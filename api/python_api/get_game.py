import uuid
import boto3
from boto3.dynamodb.conditions import Key
import time
import json
import decimal

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table("games")

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


def internal_error_payload(err, message=None):
    body = "Internal Lambda function error: {}".format(err)
    if message:
        body = "{}\n{}".format(body, message)
    return response_payload(500, body)


def request_error_payload(request, message=None):
    body = "Bad request payload: '{}'".format(request)
    if message:
        body = "{}\n{}".format(body, message)
    return response_payload(400, body)


def parameter_error_payload(param_key, param_value, message=None):
    body = "Bad input value in '{}': {}".format(param_key, param_value)
    if message:
        body = "{}\n{}".format(body, message)
    return response_payload(400, body)


def parse_event(event):
    # Basic input validation
    if not isinstance(event, dict):
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


def is_valid_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


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


def get_revealed_hands(game, round, current_round, current_status, player_authenticated, player_nickname):
    revealed_hands = []
    if round < current_round or current_status == "Finished":
        revealed_hands = [hand for hand in game["hands"] if is_active_player(game["players"], hand["player"])]
    elif player_authenticated and round == current_round:
        revealed_hands = [hand for hand in game["hands"] if is_active_player(game["players"], hand["player"]) and hand["player"] == player_nickname]
    return revealed_hands


def get_from_dynamodb(game_uuid):
    response = table.query(KeyConditionExpression=Key('game_uuid').eq(game_uuid))
    items = response.get("Items")
    if len(items) == 1:
        return items[0]
    return None


def update_in_dynamodb(game_uuid, public):
    table.update_item(
        Key={
            'game_uuid': game_uuid
        },
        UpdateExpression="set last_modified = :last_modified, #game_public = :public",
        ExpressionAttributeValues={
            ':last_modified': round(time.time()),
            ':public': public
        },
        ExpressionAttributeNames={
            '#game_public': "public"
        },
        ReturnValues="NONE"
    )
    return True


def lambda_handler(event, context):
    try:
        body = parse_event(event)
        if not body:
            return request_error_payload(event)

        game_uuid = str(body.get("game_uuid"))
        if not is_valid_uuid(game_uuid):
            return parameter_error_payload("game_uuid", game_uuid, message="Invalid game UUID")

        game = get_from_dynamodb(game_uuid)
        if not game:
            return parameter_error_payload("game_uuid", game_uuid, message="Game does not exist")

        current_status = game.get("status")

        player_uuid = body.get("player_uuid")

        if player_uuid and not is_valid_uuid(player_uuid):
            return parameter_error_payload("player_uuid", player_uuid, message="Invalid player UUID")

        round = body.get("round")

        if round:
            if isinstance(round, str) and round.isdigit():
                round = int(round)
            elif isinstance(round, int):
                pass
            else:
                return parameter_error_payload("round", round)

        if round is not None and round <= 0:
            return parameter_error_payload("round", round, message="The round parameter is invalid - must be an integer between 1 and the current round, or -1, or blank")
        current_round = game["round_number"]
        if round and current_round < round:
            return parameter_error_payload("round", round, message="The game has not reached this round")

        if round and (round != current_round or current_status != "Running"):
            game = get_from_dynamodb(f"{game_uuid}_{round}")
        else:
            round = current_round

        if player_uuid:
            player_nickname = get_nickname_by_uuid(game["players"], player_uuid)
            player_authenticated = bool(player_nickname)
            if not player_authenticated:
                return parameter_error_payload("player_uuid", player_uuid, message="The UUID does not match any active player")
        else:
            player_authenticated = False
            player_nickname = ''

        revealed_hands = get_revealed_hands(game, round, current_round, current_status, player_authenticated, player_nickname)

        private_players = []
        for player in game["players"]:
            private_players.append({key: player[key] for key in player if key != "uuid"})

        visible_game = {
            "admin_nickname": game["admin_nickname"],
            "public": game["public"],
            "status": game["status"],
            "round_number": game["round_number"],
            "max_cards": game["max_cards"],
            "players": private_players,
            "hands": revealed_hands,
            "cp_nickname": game["cp_nickname"],
            "history": game["history"]
        }

        return response_payload(200, visible_game)

    except Exception as err:
        raise
        return internal_error_payload(err)
