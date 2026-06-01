import os
import boto3
from botocore.exceptions import ClientError
import json
import re
from shared.response import response_payload, parameter_error_payload, error_payload, internal_error_payload, DecimalEncoder
from shared.constants import GameStatus, SpecialNicknames
from shared.game import get_nickname_by_uuid, get_player_by_nickname
from shared.inputs import is_valid_uuid
from shared.logging import logger
from shared.decorators import validate_game_request


sqs_client = boto3.client("sqs")
REACTION_QUEUE_NAME = os.environ.get("reaction_queue_name")

# Cached lazily on first use so the queue URL is resolved once per container
# (and captured by the SnapStart snapshot) instead of on every reaction sent.
_reaction_queue_url = None

pattern = r"^(😮|🤨|👏|😂|🦊|👍|😑|😎|😅|😭|⏳|👋|🔥|👀|🤔|🤬|😈|😇|✔️|✖️)$"

def is_safe_message(message):
    return bool(re.fullmatch(pattern, message))


def get_reaction_queue_url():
    """
    Returns the URL of an existing Amazon SQS queue, caching it after the
    first successful lookup to avoid a GetQueueUrl call on every invocation.
    """
    global _reaction_queue_url
    if _reaction_queue_url is None:
        try:
            _reaction_queue_url = sqs_client.get_queue_url(QueueName=REACTION_QUEUE_NAME)['QueueUrl']
        except ClientError:
            return None
    return _reaction_queue_url


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


@validate_game_request()
def lambda_handler(event, context, body, game):
    try:
        target = body.get("target")
        if target:
            if target == SpecialNicknames.COMMON_HAND:
                if game.get("status") == GameStatus.NOT_STARTED:
                    return error_payload(403, "The common hand is not active yet")
            else:
                player_nicknames = [p["nickname"] for p in game.get("players", [])]
                if target not in player_nicknames:
                    return parameter_error_payload("target", target, message="Target nickname does not exist")

        player_uuid = body.get("player_uuid")
        declared_nickname = body.get("nickname")
        nickname_authenticated = "false"
        player_nickname = None

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

        team_only = body.get("team_only") in ["true", True]
        sender_team = None
        if player_uuid and player_nickname:
            sender_team = get_player_by_nickname(game.get("players", []), player_nickname).get("team")
        if team_only and sender_team is None:
            return error_payload(400, "You must be on a team to send a team-only reaction")

        message_payload = {
            "game_uuid": game["game_uuid"], 
            "nickname": declared_nickname, 
            "reaction": reaction, 
            "nickname_authenticated": nickname_authenticated,
            "target_team": sender_team if team_only else None
        }
        
        if target:
            message_payload["target"] = target

        send_queue_message(message_payload)

        return response_payload(200, {"message": "Reaction received"})

    except Exception as err:
        return internal_error_payload(err)
