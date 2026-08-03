from shared.response import response_payload, parameter_error_payload, error_payload, conflict_payload, internal_error_payload
from shared.db import update_players_conditionally
from shared.constants import GameStatus
from shared.game import calculate_actual_max_cards, get_player_by_nickname
from shared.decorators import validate_game_request

@validate_game_request(
    require_player=True, 
    required_status=GameStatus.NOT_STARTED, 
    status_error_message="Players can only be removed before the game starts"
)
def lambda_handler(event, context, body, game):
    try:
        players = game.get("players", [])
        requester_nickname = body["player_nickname"]

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

        new_players = [p for p in players if p["nickname"] != target_nickname]
        
        # Admin delegation: If the admin is leaving, assign the next human player as admin
        current_admin = game.get("admin_nickname")
        new_admin = current_admin
        
        if target_nickname == current_admin:
            remaining_humans = [p for p in new_players if not p.get("ai_agent")]
            new_admin = remaining_humans[0]["nickname"] if remaining_humans else None

        # Recalculate max cards based on new player count
        rules = game.get("rules", {})
        max_cards = calculate_actual_max_cards(rules, len(new_players))

        if not update_players_conditionally(game["game_uuid"], new_players, game["last_modified"], admin_nickname=new_admin, max_cards=max_cards):
            return conflict_payload()

        return response_payload(200, {"message": f"Player {target_nickname} removed successfully"})

    except Exception as err:
        return internal_error_payload(err)
