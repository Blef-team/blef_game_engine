import os
import boto3
from botocore.exceptions import ClientError
import json
from random import sample
import re
from shared.response import * 
from shared.db import get_from_dynamodb
from shared.api_gateway import parse_event
from shared.game import get_nickname_by_uuid
from shared.inputs import is_valid_uuid
from shared.logging import logger


sqs_client = boto3.client("sqs")
REACTION_QUEUE_NAME = os.environ.get("reaction_queue_name")

pattern = r"^(😮|🤨|👏|😂|🦊|👍|😑|😎|😅)$"

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
            if not player_nickname:
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
