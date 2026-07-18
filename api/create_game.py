import decimal
import uuid
import random
import time
from botocore.exceptions import ClientError
from shared.response import error_payload, internal_error_payload, parameter_error_payload, request_error_payload, response_payload, nickname_rejected_payload
from shared.profanity_filter import is_offensive
from shared.inputs import parse_nickname
from shared.constants import GameStatus, RuleValues
from shared.db import get_from_dynamodb, save_in_dynamodb, table
from shared.game import create_player
from shared.api_gateway import parse_event

def register_rematch(prev_game, initiator_uuid, new_game_uuid):
    """
    Verifies the initiator was a player in the previous game and
    atomically registers the rematch link.
    """
    # Verify the initiator was a player in that game
    player_uuids = [p["uuid"] for p in prev_game.get("players", [])]
    if initiator_uuid not in player_uuids:
        return False, None, "You must have been a player in the previous game to start a rematch"

    # Check if a rematch is already registered
    existing_rematch = prev_game.get("next_game_uuid")
    if existing_rematch:
        return False, existing_rematch, "Rematch already exists"

    # Attempt atomic registration
    try:
        table.update_item(
            Key={'game_uuid': prev_game["game_uuid"]},
            UpdateExpression="SET next_game_uuid = :n, last_modified = :t",
            ConditionExpression="attribute_not_exists(next_game_uuid) OR attribute_type(next_game_uuid, :null_type)",
            ExpressionAttributeValues={
                ':n': new_game_uuid,
                ':t': decimal.Decimal(str(time.time())),
                ':null_type': 'NULL'
            }
        )
        return True, new_game_uuid, None
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            # Re-fetch only in case of a race condition to get the winner's UUID
            updated_prev = get_from_dynamodb(prev_game["game_uuid"])
            return False, updated_prev.get("next_game_uuid"), "Rematch already exists"
        raise

def lambda_handler(event, context):
    try:
        body = parse_event(event)
        if not body:
            return request_error_payload(event)

        game_uuid = str(uuid.uuid4())
        prev_game_uuid = body.get("previous_game_uuid")
        prev_player_uuid = body.get("previous_player_uuid")

        # Initialise rules with defaults
        rules_to_use = {
            "time_limit": RuleValues.TIME_LIMIT_DEFAULT,
            "deck_size": RuleValues.DECK_SIZE_DEFAULT,
            "common_cards": RuleValues.COMMON_CARDS_DEFAULT,
            "jokers": RuleValues.JOKERS_DEFAULT,
            "blanks": RuleValues.BLANKS_DEFAULT,
            "max_cards_preference": RuleValues.MAX_CARDS_PREFERENCE_DEFAULT
        }

        if prev_game_uuid:
            prev_game = get_from_dynamodb(prev_game_uuid)
            if not prev_game:
                return error_payload(404, "Previous game not found")
            
            # Inherit rules from the previous session
            if "rules" in prev_game:
                rules_to_use = prev_game["rules"]
            
            # Rematch validation and registration
            if not prev_player_uuid:
                return parameter_error_payload("previous_player_uuid", None, "Required for rematch")

            success, final_uuid, error_msg = register_rematch(prev_game, prev_player_uuid, game_uuid)
            if not success:
                if final_uuid: # Someone else already created it
                    return response_payload(200, {"game_uuid": final_uuid, "message": error_msg})
                return error_payload(403, error_msg) # Unauthorized or missing game
            
        game = {
            "game_uuid": game_uuid,
            "next_game_uuid": None,
            "admin_nickname": None,
            "public": "false",
            "room": random.randrange(10, 100),
            "status": GameStatus.NOT_STARTED,
            "round_number": 0,
            "max_cards": 0,
            "players": [],
            "hands": [],
            "cp_nickname": None,
            "history": [],
            "rules": rules_to_use
        }

        nickname = body.get("nickname")
        if not nickname:
            if save_in_dynamodb(game):
                return response_payload(200, {"game_uuid": game_uuid})
            raise Exception("Failed to save game")

        # If the user wants to join at the same time
        try:
            nickname = parse_nickname(nickname)
        except ValueError as err:
            return parameter_error_payload("nickname", nickname, message=str(err))

        if is_offensive(nickname):
            return nickname_rejected_payload(reason="profanity")

        player = create_player(game, nickname)
        game.update({"players": [player], "admin_nickname": player.get("nickname")})
        if save_in_dynamodb(game):
            return response_payload(200, {"game_uuid": game_uuid, "player_uuid": player.get("uuid")})

        raise Exception("Something went wrong - ended up with no response")

    except Exception as err:
        return internal_error_payload(err)
