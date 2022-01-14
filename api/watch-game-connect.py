import uuid
import boto3
from boto3.dynamodb.conditions import Key
import time
import json
import decimal

dynamodb = boto3.resource('dynamodb')
games_table = dynamodb.Table("games")
websocket_table = dynamodb.Table("watch_game_websocket_manager")

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


def get_game(game_uuid):
    response = games_table.query(KeyConditionExpression=Key('game_uuid').eq(game_uuid))
    items = response.get("Items")
    if len(items) == 1:
        return items[0]
    return None


def save_connection_object(obj):
    obj["last_modified"] = time.time()
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



def get_nickname_by_uuid(players, player_uuid):
    filtered_players = [p for p in players if p["uuid"] == player_uuid]
    if filtered_players:
        return filtered_players[0]["nickname"]


def register_game_watcher(game_uuid, player_uuid, connection_id):
    if game_uuid and not is_valid_uuid(game_uuid):
        return parameter_error_payload("game_uuid", game_uuid, message="Invalid game UUID")

    game = get_game(game_uuid)
    if not game:
        return parameter_error_payload("game_uuid", game_uuid, message="Game does not exist")

    if player_uuid:
        if not is_valid_uuid(player_uuid):
            return parameter_error_payload("player_uuid", player_uuid, message="Invalid player UUID")
        player_nickname = get_nickname_by_uuid(game["players"], player_uuid)
        player_authenticated = bool(player_nickname)
        if not player_authenticated:
            return parameter_error_payload("player_uuid", player_uuid, message="The UUID does not match any active player")

    connection_object = {
        "connection_id": connection_id,
        "game_uuid": game_uuid,
        "player_uuid": player_uuid
    }

    if save_connection_object(connection_object):
        return response_payload(200, {"message": "Connected"})


def register_public_games_watcher(connection_id):
    connection_object = {
        "connection_id": connection_id
    }

    if save_connection_object(connection_object):
        return response_payload(200, {"message": "Connected"})


def register_watcher(game_uuid, player_uuid, connection_id):
    if not game_uuid and not player_uuid:
        payload = register_public_games_watcher(connection_id)
    else:
        payload = register_game_watcher(game_uuid, player_uuid, connection_id)

    if payload:
        return payload


def lambda_handler(event, context):
    try:
        body = parse_event(event)

        connection_id = get_connection_id(event, context, body)

        game_uuid = event.get("headers", {}).get("game_uuid") if "game_uuid" not in body else body["game_uuid"]
        player_uuid = event.get("headers", {}).get("player_uuid") if "player_uuid" not in body else body["player_uuid"]

        payload = register_watcher(game_uuid, player_uuid, connection_id)

        if payload:
            return payload

        raise(Exception("Something went wrong - ended up with no response"))

    except Exception as err:
        return internal_error_payload(err)
