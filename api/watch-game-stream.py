import os
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
import json
from shared.response import * 
from shared.api_gateway import parse_event
from shared.game import get_player_by_nickname, get_nickname_by_uuid, censor_game
from shared.logging import logger
from shared.db import websocket_table

sqs_client = boto3.client("sqs")
AIAGENT_QUEUE_NAME = os.environ.get("aiagent_queue_name")

watch_game_websocket_api_id = os.environ.get("watch_game_websocket_api_id")
watch_game_websocket_api_stage = os.environ.get("watch_game_websocket_api_stage")

endpoint_url = f"{boto3.client('apigatewayv2').get_api(ApiId=watch_game_websocket_api_id).get('ApiEndpoint')}/{watch_game_websocket_api_stage}".replace("wss://", "https://")
apigateway = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)

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


def find_connected_players(game):
    game_uuid = game["game_uuid"]
    if isinstance(game_uuid, dict):
        game_uuid = game_uuid.get("S")
    watched_game_uuid = game_uuid.split("_")[0]
    response = websocket_table.query(
        KeyConditionExpression=Key('game_uuid').eq(watched_game_uuid),
        IndexName="game_uuid-index"
    )
    return [(connection["connection_id"], connection["player_uuid"]) for connection in response.get("Items", [])]


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
    return game.get("public") == "true" or game_old.get("public") == "true"


def find_connected_public_games_watchers():
    response = websocket_table.scan(
        FilterExpression=Attr('game_uuid').not_exists()
    )
    return [(connection["connection_id"]) for connection in response.get("Items")]


def post_to_connection(payload, connection_id):
    logger.info('## POSTING TO CONNECTION')
    logger.info(connection_id)
    try:
        response = apigateway.post_to_connection(
            Data=bytes(json.dumps(response_payload(200, payload), cls=DecimalEncoder), encoding="utf-8"),
            ConnectionId=connection_id
        )
    except Exception as err:
        logger.info('## ERROR: COULD NOT POST TO CONNECTION')
        logger.info(str(err))
    return True


def deserialise_dynamodb_stream_event(obj):
    return {k: deserializer.deserialize(v) for k,v in obj.items()}


def update_game_watchers(game):
    connected_players = find_connected_players(game)
    logger.info('## CONNECTED PLAYERS')
    logger.info(connected_players)
    for connection_id, player_uuid in connected_players:
        player_nickname = get_nickname_by_uuid(game["players"], player_uuid)
        player_authenticated = bool(player_nickname)
        current_round = game["round_number"] + 1 if any(str(val["action_id"])=="89" for val in game.get("history")) else game["round_number"]
        visible_game = censor_game(game, current_round, player_authenticated, player_nickname)
        post_to_connection(visible_game, connection_id)


def update_public_games_watchers(game, game_old):
    logger.info('## UPDATING PUBLIC GAMES WATCHERS')
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
    if not current_player:
        logger.info('## THERE IS NO CURRENT PLAYER:')
        return
    player_obj = get_player_by_nickname(game["players"], current_player)
    if not player_obj.get("ai_agent"):
        logger.info('## THE CURRENT PLAYER IS NOT AN AI AGENT')
        return
    logger.info('## AI AGENT UUID:')
    logger.info(player_obj.get("uuid"))
    return player_obj.get("uuid")


def queue_aiagent(game):
    if get_aiagent_player_uuid(game["new"]):
        logger.info('## SENDING AI AGENT QUEUE MESSAGE')
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
            logger.info('## UPDATING WATCHERS')
            update_watchers(game)
            logger.info('## QUEUEING AI IF NEEDED')
            queue_aiagent(game)

        return response_payload(200, {"message": "All watchers updated"})

    except Exception as err:
        return internal_error_payload(err)
