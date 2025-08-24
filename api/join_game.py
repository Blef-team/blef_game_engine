import uuid
import time
import re
import decimal
from botocore.exceptions import ClientError
from shared.response import *
from shared.db import table, get_from_dynamodb
from shared.api_gateway import parse_event
from shared.constants import GameStatus
from shared.game import calculate_actual_max_cards
from shared.inputs import is_valid_uuid
from shared.logging import logger

def update_in_dynamodb(game_uuid, players, admin_nickname, max_cards, last_modified):
    """
    Conditionally updates the game state in DynamoDB to add a new player.
    Returns True on success, False on failure (due to a race condition).
    """
    try:
        table.update_item(
            Key={'game_uuid': game_uuid},
            UpdateExpression="SET players = :p, last_modified = :t, admin_nickname = :a, max_cards = :mc",
            ConditionExpression="last_modified = :lm",
            ExpressionAttributeValues={
                ':p': players,
                ':t': decimal.Decimal(str(time.time())),
                ':a': admin_nickname,
                ':mc': max_cards,
                ':lm': last_modified
            }
        )
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            logger.warning(f"Failed to join game {game_uuid} due to a race condition.")
            return False
        else:
            raise

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

        if game.get("status") != GameStatus.NOT_STARTED:
            return error_payload(403, "Game already started")

        if len(game.get("players")) == 8:
            return error_payload(403, "Game room full")

        nickname = body.get("nickname")
        if not nickname:
            return parameter_error_payload("nickname", nickname, message="Nickname missing - please supply it")
        if not isinstance(nickname, str):
            return parameter_error_payload("nickname", nickname, message="Nickname invalid")
        if not re.match("^[a-zA-Z]\w*$", nickname):
            return parameter_error_payload("nickname", nickname, message="Nickname must start with a letter and only contain alphanumeric characters")

        players = game.get("players")
        if nickname in [p["nickname"] for p in players]:
            return parameter_error_payload("nickname", nickname, message="Nickname already taken")

        player_uuid = str(uuid.uuid4())
        players.append({"uuid": player_uuid, "nickname": nickname, "n_cards": 0, "ready": False})
        admin_nickname = game.get("admin_nickname") or nickname
        max_cards = calculate_actual_max_cards(game.get("rules", {}), len(players))

        if update_in_dynamodb(game_uuid, players, admin_nickname, max_cards, game["last_modified"]):
            return response_payload(200, {"player_uuid": player_uuid})
        
        logger.info(f"Join failed for '{nickname}' due to race condition.")
        return error_payload(409, "The game state changed. Please try again.")

    except Exception as err:
        return internal_error_payload(err)
