import uuid
import boto3
from boto3.dynamodb.conditions import Key
import time
import re
import json

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table("games")

def response_payload(status_code, body):
    return {
            'statusCode': status_code,
            'body': json.dumps(body),
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


def get_from_dynamodb(game_uuid):
    response = table.query(KeyConditionExpression=Key('game_uuid').eq(game_uuid))
    items = response.get("Items")
    if len(items) == 1:
        return items[0]
    return None


def update_in_dynamodb(game_uuid, players, admin_nickname):
    table.update_item(
        Key={
            'game_uuid': game_uuid
        },
        UpdateExpression="set players = :players, last_modified = :last_modified, admin_nickname = :admin_nickname",
        ExpressionAttributeValues={
            ':players': players,
            ':last_modified': round(time.time()),
            ':admin_nickname': admin_nickname
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

        if game.get("status") != "Not started":
            return response_payload(403, "Game already started")

        if len(game.get("players")) == 8:
            return response_payload(403, "Game room full")

        nickname = str(body.get("nickname"))
        if not nickname:
            return parameter_error_payload("nickname", nickname, message="Nickname missing - please supply it")
        if not re.match("^[a-zA-Z]\w*$", nickname):
            return parameter_error_payload("nickname", nickname, message="Nickname must start with a letter and only contain alphanumeric characters")

        players = game.get("players")
        if nickname in [p["nickname"] for p in players]:
            return parameter_error_payload("nickname", nickname, message="Nickname already taken")

        player_uuid = str(uuid.uuid4())
        player = {"uuid": player_uuid, "nickname": nickname, "n_cards": 0}
        players.append(player)

        admin_nickname = game.get("admin_nickname")
        if len(players) == 1:
            admin_nickname = nickname

        update_in_dynamodb(game_uuid, players, admin_nickname)

        response = {"player_uuid": player_uuid}
        return response_payload(200, response)

    except Exception as err:
        return internal_error_payload(err)
