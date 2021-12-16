import os
import uuid
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
import time
import json
import decimal
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


sqs_client = boto3.client("sqs")
AIAGENT_QUEUE_NAME = os.environ.get("aiagent_queue_name")

watch_game_websocket_api_id = os.environ.get("watch_game_websocket_api_id")
watch_game_websocket_api_stage = os.environ.get("watch_game_websocket_api_stage")

endpoint_url = f"{boto3.client('apigatewayv2').get_api(ApiId=watch_game_websocket_api_id).get('ApiEndpoint')}/{watch_game_websocket_api_stage}".replace("wss://", "https://")
apigateway = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)

dynamodb = boto3.resource('dynamodb')
games_table = dynamodb.Table("games")
websocket_table = dynamodb.Table("watch_game_websocket_manager")

deserializer = boto3.dynamodb.types.TypeDeserializer()


def get_aiagent_queue_url():
    """
    Returns the URL of an existing Amazon SQS queue.
    """
    try:
        return sqs_client.get_queue_url(QueueName=AIAGENT_QUEUE_NAME)['QueueUrl']
    except ClientError:
        return


def send_queue_message(game):
    """
    Sends a message to the AI agent queue.
    """
    try:
        logger.info('## QUEUE URL')
        logger.info(get_aiagent_queue_url())
        logger.info('## GAME')
        logger.info(game)
        logger.info('## GAME UUID')
        logger.info(game["game_uuid"])
        sqs_client.send_message(QueueUrl=get_aiagent_queue_url(),
                                MessageBody=json.dumps(game, cls=DecimalEncoder),
                                MessageGroupId=game["game_uuid"])
    except ClientError:
        return


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return int(obj)
        return super(DecimalEncoder, self).default(obj)


def response_payload(status_code, body):
    return {
            'statusCode': status_code,
            'body': json.dumps(body, cls=DecimalEncoder),
            'headers': {
                'Access-Control-Allow-Headers':'Content-Type,X-Amz-Date,Authorization,X-Api-Key,x-api-key,X-Amz-Security-Token',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
                'Access-Control-Allow-Credentials': True,
                'Content-Type': 'application/json'
            },
        }


def error_payload(status_code, body):
    return response_payload(status_code, {"error": body})


def internal_error_payload(err, message=None):
    body = "Internal Lambda function error: {}".format(err)
    if message:
        body = "{}\n{}".format(body, message)
    return error_payload(500, body)


def request_error_payload(request, message=None):
    body = "Bad request payload: '{}'".format(request)
    if message:
        body = "{}\n{}".format(body, message)
    return error_payload(400, body)


def parameter_error_payload(param_key, param_value, message=None):
    body = "Bad input value in '{}': {}".format(param_key, param_value)
    if message:
        body = "{}\n{}".format(body, message)
    return error_payload(400, body)


def is_valid_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def parse_event(event):
    # Basic input validation
    if not isinstance(event, dict):
        if isinstance(event, str):
            return json.loads(event)
        return False

    # Handle both direct triggers and API Gateway
    body = event.get("body", event)
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError:
            return None
    path_params = event.get("pathParameters", {})
    query_params = event.get("queryStringParameters", {})
    body.update(path_params)
    body.update(query_params)
    return body

def find_connected_players(game):
    game_uuid = game["game_uuid"]
    if isinstance(game_uuid, dict):
        game_uuid = game_uuid.get("S")
    response = websocket_table.query(
        KeyConditionExpression=Key('game_uuid').eq(game_uuid),
        IndexName="game_uuid-index"
    )
    return [(connection["connection_id"], connection["player_uuid"]) for connection in response.get("Items")]


def save_connection_object(obj):
    obj["last_modified"] = round(time.time())
    websocket_table.put_item(Item=obj)
    return True


def get_connection_id(event, context, body):
    if context and hasattr(context, 'get') and context.get("connectionId"):
        return context.get("connectionId")
    if "connectionId" in event.get("requestContext", {}):
        return event["requestContext"]["connectionId"]
    if "connectionId" in event:
        return event["connectionId"]
    if "connectionId" in body:
        return body["connectionId"]
    raise ValueError("Request context is invalid!")


def get_player_by_nickname(players, nickname):
    filtered_players = [p for p in players if p["nickname"] == nickname]
    if filtered_players:
        return filtered_players[0]


def get_nickname_by_uuid(players, player_uuid):
    filtered_players = [p for p in players if p["uuid"] == player_uuid]
    if filtered_players:
        return filtered_players[0]["nickname"]


def is_active_player(players, nickname):
    player = get_player_by_nickname(players, nickname)
    if player:
        return player["n_cards"] != 0
    return False


def get_revealed_hands(game, current_round, current_status, player_authenticated, player_nickname):
    revealed_hands = []
    if game["round_number"] < current_round or current_status == "Finished":
        revealed_hands = [hand for hand in game["hands"] if is_active_player(game["players"], hand["nickname"])]
    elif player_authenticated and game["round_number"] == current_round:
        revealed_hands = [hand for hand in game["hands"] if is_active_player(game["players"], hand["nickname"]) and hand["nickname"] == player_nickname]
    return revealed_hands


def censor_game(game, current_round, player_authenticated, player_nickname):
    revealed_hands = get_revealed_hands(game, current_round, game["status"], player_authenticated, player_nickname)

    private_players = []
    for player in game["players"]:
        private_players.append({key: player[key] for key in player if key != "uuid"})

    return {
        "admin_nickname": game["admin_nickname"],
        "public": game["public"],
        "room": game["room"],
        "status": game["status"],
        "round_number": game["round_number"],
        "max_cards": game["max_cards"],
        "players": private_players,
        "hands": revealed_hands,
        "cp_nickname": game["cp_nickname"],
        "history": game["history"],
        "last_modified": game["last_modified"]
    }


def get_public_game_info(game):
    public_game_info = {
        "game_uuid": game["game_uuid"],
        "room": game["room"],
        "public": game["public"],
        "last_modified": game["last_modified"]
    }
    if game["public"]:
        public_game_info["players"] = [p["nickname"] for p in game["players"]]
    return public_game_info


def can_get_public_info(game, game_old):
    return game["public"] == "true" or game_old["public"] == "true"


def find_connected_public_games_watchers():
    response = websocket_table.scan(
        FilterExpression=Attr('game_uuid').not_exists()
    )
    return [(connection["connection_id"]) for connection in response.get("Items")]


def post_to_connection(payload, connection_id):
    response = apigateway.post_to_connection(
        Data=bytes(json.dumps(response_payload(200, payload), cls=DecimalEncoder), encoding="utf-8"),
        ConnectionId=connection_id
    )
    return True


def deserialise_dynamodb_stream_event(obj):
    return {k: deserializer.deserialize(v) for k,v in obj.items()}


def update_game_watchers(game):
    connected_players = find_connected_players(game)
    for connection_id, player_uuid in connected_players:
        player_nickname = get_nickname_by_uuid(game["players"], player_uuid)
        player_authenticated = bool(player_nickname)
        visible_game = censor_game(game, game["round_number"], player_authenticated, player_nickname)
        post_to_connection(visible_game, connection_id)


def update_public_games_watchers(game, game_old):
    if not can_get_public_info(game, game_old):
        return
    connected_watchers = find_connected_public_games_watchers()
    for connection_id in connected_watchers:
        public_game_info = get_public_game_info(game)
        post_to_connection(public_game_info, connection_id)


def update_watchers(game):
    update_game_watchers(game["new"])
    update_public_games_watchers(game["new"], game["old"])


def get_aiagent_player_uuid(game):
    current_player = game["cp_nickname"]
    player_obj = get_player_by_nickname(game["players"], current_player)
    if not player_obj.get("ai_agent"):
        return
    return player_obj.get("uuid")


def queue_aiagent(game):
    if get_aiagent_player_uuid(game["new"]):
        send_queue_message(game["new"])


def lambda_handler(event, context):
    try:
        logger.info('## EVENT')
        logger.info(event)
        games_objects = [obj["dynamodb"] for obj in parse_event(event).get("Records") if "dynamodb" in obj]
        games = [
            {
                "new": deserialise_dynamodb_stream_event(obj.get("NewImage", {})),
                "old": deserialise_dynamodb_stream_event(obj.get("OldImage", {}))
            }
            for obj in games_objects
        ]
        for game in games:
            logger.info('## GAME')
            logger.info(game)
            update_watchers(game)
            queue_aiagent(game)

        return response_payload(200, {"message": "All watchers updated"})

    except Exception as err:
        return internal_error_payload(err)
