import time
import decimal
from shared.response import *
from shared.db import table, get_from_dynamodb
from shared.api_gateway import parse_event
from shared.constants import GameStatus
from shared.game import get_nickname_by_uuid, get_player_by_nickname, unset_human_readiness
from shared.inputs import is_valid_uuid

def update_in_dynamodb(game_uuid, players):
    """ Updates the players list in DynamoDB. """
    table.update_item(
        Key={'game_uuid': game_uuid},
        UpdateExpression="SET players = :p, last_modified = :t",
        ExpressionAttributeValues={
            ':p': players,
            ':t': decimal.Decimal(str(time.time()))
        }
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

        if game.get("status") != GameStatus.NOT_STARTED:
            return error_payload(403, "Teams can only be changed before the game starts")

        # Validate requester UUID
        player_uuid = str(body.get("player_uuid"))
        if not is_valid_uuid(player_uuid):
            return parameter_error_payload("player_uuid", player_uuid, message="Invalid player UUID")

        players = game.get("players", [])
        requester_nickname = get_nickname_by_uuid(players, player_uuid)
        if not requester_nickname:
            return parameter_error_payload("player_uuid", player_uuid, message="Requester is not in this game")

        # Validate target nickname
        target_nickname = body.get("nickname")
        if not target_nickname:
            return parameter_error_payload("nickname", target_nickname, message="Target nickname missing")
        
        target_player = get_player_by_nickname(players, target_nickname)
        if not target_player:
            return parameter_error_payload("nickname", target_nickname, message="Target player not found in this game")

        new_team = body.get("team")
        if new_team is not None:
            try:
                new_team = int(new_team)
            except (ValueError, TypeError):
                return parameter_error_payload("team", new_team, message="Team must be an integer (1-4) or null")
        if new_team not in [1, 2, 3, 4, None]:
             return parameter_error_payload("team", new_team, message="Team must be 1, 2, 3, 4, or null")

        # Admin can change anyone's team. Non-admins can only change their own.
        is_admin = (requester_nickname == game.get("admin_nickname"))
        is_self = (requester_nickname == target_nickname)

        if not (is_admin or is_self):
            return error_payload(403, "You do not have permission to change this player's team")

        # Perform change
        target_player["team"] = new_team
        
        # Reset readiness for human players since state changed
        players = unset_human_readiness(players)

        update_in_dynamodb(game_uuid, players)

        return response_payload(200, {"message": f"Player {target_nickname} team changed successfully"})

    except Exception as err:
        return internal_error_payload(err)
