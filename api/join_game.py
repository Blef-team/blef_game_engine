import time
import decimal
from botocore.exceptions import ClientError
from shared.response import response_payload, parameter_error_payload, error_payload, internal_error_payload, nickname_rejected_payload
from shared.profanity_filter import is_offensive
from shared.inputs import parse_nickname
from shared.db import table
from shared.constants import GameStatus
from shared.game import create_player, calculate_actual_max_cards
from shared.decorators import validate_game_request
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

@validate_game_request(
    required_status=GameStatus.NOT_STARTED, 
    status_error_message="Game already started"
)
def lambda_handler(event, context, body, game):
    try:
        players = game.get("players", [])
        if len(players) == 8:
            return error_payload(403, "Game room full")

        nickname = body.get("nickname")
        if not nickname:
            return parameter_error_payload("nickname", nickname, message="Nickname missing - please supply it")
        try:
            nickname = parse_nickname(nickname)
        except ValueError as err:
            return parameter_error_payload("nickname", nickname, message=str(err))

        if is_offensive(nickname):
            return nickname_rejected_payload(reason="profanity")

        if nickname in [p["nickname"] for p in players]:
            return parameter_error_payload("nickname", nickname, message="Nickname already taken")

        new_player = create_player(game, nickname)
        players.append(new_player)
        admin_nickname = game.get("admin_nickname") or new_player.get("nickname")
        max_cards = calculate_actual_max_cards(game.get("rules", {}), len(players))

        if update_in_dynamodb(game["game_uuid"], players, admin_nickname, max_cards, game["last_modified"]):
            return response_payload(200, {"player_uuid": new_player.get("uuid")})
        
        logger.info(f"Join failed for '{nickname}' due to race condition.")
        return error_payload(409, "The game state changed. Please try again.")

    except Exception as err:
        return internal_error_payload(err)
