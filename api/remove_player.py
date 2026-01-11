import time
import decimal
from shared.response import *
from shared.db import table, get_from_dynamodb
from shared.api_gateway import parse_event
from shared.constants import GameStatus
from shared.game import calculate_actual_max_cards, get_nickname_by_uuid, get_player_by_nickname
from shared.inputs import is_valid_uuid

def update_in_dynamodb(game_uuid, players, admin_nickname, max_cards):
    """ Updates the players list, admin, and max_cards in DynamoDB. """
    table.update_item(
        Key={'game_uuid': game_uuid},
        UpdateExpression="SET players = :p, admin_nickname = :a, max_cards = :mc, last_modified = :t",
        ExpressionAttributeValues={
            ':p': players,
            ':a': admin_nickname,
            ':mc': max_cards,
            ':t': decimal.Decimal(str(time.time()))
        }
    )
    return True

def lambda_handler(event, context):
    try:
        body = parse_event(event)
        if not body:
            return request_error_payload(event)

        # Validate game UUID
        game_uuid = str(body.get("game_uuid"))
        if not is_valid_uuid(game_uuid):
            return parameter_error_payload("game_uuid", game_uuid, message="Invalid game UUID")

        game = get_from_dynamodb(game_uuid)
        if not game:
            return parameter_error_payload("game_uuid", game_uuid, message="Game does not exist")

        if game.get("status") != GameStatus.NOT_STARTED:
            return error_payload(403, "Players can only be removed before the game starts")

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

        # Admin can remove anyone. Non-admins can only remove themselves (leave).
        is_admin = (requester_nickname == game.get("admin_nickname"))
        is_self = (requester_nickname == target_nickname)

        if not (is_admin or is_self):
            return error_payload(403, "You do not have permission to remove this player")

        # Perform removal
        new_players = [p for p in players if p["nickname"] != target_nickname]
        
        # Admin delegation: If the admin is leaving, assign the next human player as admin
        current_admin = game.get("admin_nickname")
        new_admin = current_admin
        
        if target_nickname == current_admin:
            remaining_humans = [p for p in new_players if not p.get("ai_agent")]
            if remaining_humans:
                new_admin = remaining_humans[0]["nickname"]
            else:
                new_admin = None

        # Recalculate max cards based on new player count
        rules = game.get("rules", {})
        max_cards = calculate_actual_max_cards(rules, len(new_players))

        update_in_dynamodb(game_uuid, new_players, new_admin, max_cards)

        return response_payload(200, {"message": f"Player {target_nickname} removed successfully"})

    except Exception as err:
        return internal_error_payload(err)
