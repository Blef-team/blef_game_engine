import os
import time
import json
import uuid
import boto3
from boto3.dynamodb.conditions import Key


AGENT_MAPPING = json.loads(os.environ.get("agent_mapping"))

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


def update_in_dynamodb(game_uuid, players):
    table.update_item(
        Key={
            'game_uuid': game_uuid
        },
        UpdateExpression="set players = :players, last_modified = :last_modified",
        ExpressionAttributeValues={
            ':players': players,
            ':last_modified': decimal.Decimal(str(time.time()))
        },
        ReturnValues="NONE"
    )
    return True


def format_name(agent_name, num):
    enumerated_name = f"{agent_name}_{num+1}" if num else agent_name
    return f"{enumerated_name}_(AI)"


def set_nickname(agent_name, player_nicknames, i=0):
    """ Create an AI agent nickname """
    formatted_name = format_name(agent_name, i)
    if formatted_name in player_nicknames:
        return set_nickname(agent_name, player_nicknames, i+1)
    return formatted_name


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
            return error_payload(403, "Game already started")

        admin_uuid = body.get("admin_uuid")

        if not admin_uuid:
            return parameter_error_payload("admin_uuid", admin_uuid, message="Admin UUID missing - please supply it")

        if not is_valid_uuid(admin_uuid):
            return parameter_error_payload("admin_uuid", admin_uuid, message="Invalid admin UUID")

        players = game.get("players")
        game_admin_uuid = [player["uuid"] for player in players if player["nickname"] == game.get("admin_nickname")][0]
        if game_admin_uuid != admin_uuid:
            return parameter_error_payload("admin_uuid", admin_uuid, message="Admin UUID does not match")

        if len(players) == 8:
            return error_payload(403, "Game room full")

        agent_name = body.get("agent_name")
        if not agent_name:
            return parameter_error_payload("agent_name", agent_name, message="Agent name missing - please supply it")

        agent_type = AGENT_MAPPING.get(agent_name)
        if not agent_type:
            return parameter_error_payload("agent_name", agent_type, message="Invalid agent_name")

        nickname = set_nickname(agent_name, [p["nickname"] for p in players])

        player_uuid = str(uuid.uuid4())
        player = {
            "uuid": player_uuid,
            "nickname": nickname,
            "n_cards": 0,
            "ai_agent": agent_type
            }
        players.append(player)

        update_in_dynamodb(game_uuid, players)

        payload = {"message": f"{nickname} joined the game"}
        return response_payload(200, payload)

    except Exception as err:
        return internal_error_payload(err)
