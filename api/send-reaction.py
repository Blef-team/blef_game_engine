import os
import uuid
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
import json
import decimal
from random import sample
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
import re


dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table("games")

sqs_client = boto3.client("sqs")
REACTION_QUEUE_NAME = os.environ.get("reaction_queue_name")

pattern = r"^(😮|🤨|👏|😂|🦊)$"

def is_safe_message(message):
    return bool(re.fullmatch(pattern, message))


def get_reaction_queue_url():
    """
    Returns the URL of an existing Amazon SQS queue.
    """
    try:
        return sqs_client.get_queue_url(QueueName=REACTION_QUEUE_NAME)['QueueUrl']
    except ClientError:
        return


def send_queue_message(message):
    """
    Sends a message to the AI agent queue.
    """
    try:
        logger.info('## QUEUE URL')
        logger.info(get_reaction_queue_url())
        logger.info('## MESSAGE')
        logger.info(message)
        logger.info('## GAME UUID')
        logger.info(message["game_uuid"])
        sqs_client.send_message(QueueUrl=get_reaction_queue_url(),
                                MessageBody=json.dumps(message, cls=DecimalEncoder))
    except ClientError:
        return



class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            if obj.as_tuple().exponent == 0:
                return int(obj)
            return float(obj)
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


def get_nickname_by_uuid(players, player_uuid):
    filtered_players = [p for p in players if p["uuid"] == player_uuid]
    if filtered_players:
        return filtered_players[0]["nickname"]


def get_from_dynamodb(game_uuid):
    response = table.query(KeyConditionExpression=Key('game_uuid').eq(game_uuid))
    items = response.get("Items")
    if len(items) == 1:
        return items[0]
    return None


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

        player_uuid = body.get("player_uuid")
        declared_nickname = body.get("nickname")
        nickname_authenticated = "false"

        if player_uuid and not is_valid_uuid(player_uuid):
            return parameter_error_payload("player_uuid", player_uuid, message="Invalid player UUID")
        elif player_uuid:
            player_nickname = get_nickname_by_uuid(game["players"], player_uuid)
            player_authenticated = bool(player_nickname)
            if not player_authenticated:
                return parameter_error_payload("player_uuid", player_uuid, message="The UUID does not match any active player")
            if player_nickname == declared_nickname:
                nickname_authenticated = "true"

        reaction = body.get("reaction")

        if not reaction:
            return parameter_error_payload("reaction", reaction, message="Reaction missing")
        elif not is_safe_message(reaction):
            return error_payload(400, "This reaction contains forbidden characters or forbidden content")

        print({"game_uuid": game_uuid, "nickname": declared_nickname, "reaction": reaction, "nickname_authenticated": nickname_authenticated})
        send_queue_message({"game_uuid": game_uuid, "nickname": declared_nickname, "reaction": reaction, "nickname_authenticated": nickname_authenticated})

        return response_payload(200, {"message": "Reaction received"})

    except Exception as err:
        return internal_error_payload(err)
