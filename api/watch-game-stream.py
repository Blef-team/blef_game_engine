import os
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor
import json
from shared.response import *
from shared.api_gateway import parse_event
from shared.game import get_player_by_nickname, get_nickname_by_uuid, censor_game, is_update_redundant
from shared.logging import logger
from shared.db import websocket_table
from shared.websocket import post_to_connection, broadcast_game_state, MAX_BROADCAST_WORKERS

sqs_client = boto3.client("sqs")
AIAGENT_QUEUE_NAME = os.environ.get("aiagent_queue_name")

# Cached lazily on first use so the queue URL is resolved once per container
# (and captured by the SnapStart snapshot) instead of on every broadcast.
_aiagent_queue_url = None

deserializer = boto3.dynamodb.types.TypeDeserializer()


def get_aiagent_queue_url():
    """
    Returns the URL of an existing Amazon SQS queue, caching it after the
    first successful lookup to avoid a GetQueueUrl call on every invocation.
    """
    global _aiagent_queue_url
    if _aiagent_queue_url is None:
        try:
            _aiagent_queue_url = sqs_client.get_queue_url(QueueName=AIAGENT_QUEUE_NAME)['QueueUrl']
        except ClientError:
            return None
    return _aiagent_queue_url


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
    response = websocket_table.query(
        KeyConditionExpression=Key('game_uuid').eq("LOBBY"),
        IndexName="game_uuid-index"
    )
    return [(connection["connection_id"]) for connection in response.get("Items")]


def deserialise_dynamodb_stream_event(obj):
    return {k: deserializer.deserialize(v) for k,v in obj.items()}


def update_public_games_watchers(game, game_old):
    logger.info('## UPDATING PUBLIC GAMES WATCHERS')
    if not can_get_public_info(game, game_old):
        return
    connected_watchers = find_connected_public_games_watchers()
    if not connected_watchers:
        return
    public_game_info = get_public_game_info(game)
    with ThreadPoolExecutor(max_workers=min(len(connected_watchers), MAX_BROADCAST_WORKERS)) as executor:
        list(executor.map(lambda connection_id: post_to_connection(public_game_info, connection_id), connected_watchers))


def update_watchers(game):
    broadcast_game_state(game["new"])
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

            # If it's a timed game, it's the EOR state and the game isn't about to finish, skip update
            # That's because this state will cause a flicker at best (fraction of a second before the 'waiting state') or glitching UI at worst
            new_game_state = game.get("new", {})
            if not new_game_state:
                continue
            if is_update_redundant(new_game_state):
                logger.info('## SKIPPING REDUNDANT UPDATE')
                continue

            logger.info('## UPDATING WATCHERS')
            update_watchers(game)
            logger.info('## QUEUEING AI IF NEEDED')
            queue_aiagent(game)

        return response_payload(200, {"message": "All watchers updated"})

    except Exception as err:
        return internal_error_payload(err)
