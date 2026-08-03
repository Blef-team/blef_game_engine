from shared.response import response_payload, parameter_error_payload, error_payload, internal_error_payload
from shared.db import update_players_conditionally
from shared.constants import GameStatus
from shared.game import get_player_by_nickname, unset_human_readiness
from shared.inputs import parse_team
from shared.decorators import validate_game_request

@validate_game_request(
    require_player=True, 
    required_status=GameStatus.NOT_STARTED, 
    status_error_message="Teams can only be changed before the game starts"
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

        try:
            new_team = parse_team(body.get("team"))
        except ValueError as err:
            return parameter_error_payload("team", body.get("team"), message=str(err))

        # Admin can change anyone's team. Non-admins can only change their own.
        is_admin = (requester_nickname == game.get("admin_nickname"))
        is_self = (requester_nickname == target_nickname)

        if not (is_admin or is_self):
            return error_payload(403, "You do not have permission to change this player's team")

        target_player["team"] = new_team
        players = unset_human_readiness(players)

        if not update_players_conditionally(game["game_uuid"], players, game["last_modified"]):
            return error_payload(409, "The game state changed. Please try again.")

        return response_payload(200, {"message": f"Player {target_nickname} team changed successfully"})

    except Exception as err:
        return internal_error_payload(err)
