from shared.response import response_payload, error_payload, internal_error_payload
from shared.constants import GameStatus, RuleValues
from shared.game import start_game
from shared.decorators import validate_game_request

@validate_game_request(
    require_admin=True, 
    required_status=GameStatus.NOT_STARTED, 
    status_error_message="Game already started"
)
def lambda_handler(event, context, body, game):
    try:
        players = game.get("players", [])
        n_players = len(players)
        
        if n_players < 2:
            return error_payload(403, "At least 2 players needed to start a game")

        teams = [p.get("team") for p in players]
        non_null_teams = [t for t in teams if t is not None]
        if len(non_null_teams) == n_players and len(set(non_null_teams)) == 1:
            return error_payload(403, "Cannot start a game where all players are on the same team")

        if int(game.get("rules", {}).get("time_limit", RuleValues.TIME_LIMIT_DEFAULT)) > RuleValues.TIME_LIMIT_NO_LIMIT:
            return error_payload(403, "Games with a time limit can only start when everyone is ready")

        if not start_game(game):
            return error_payload(409, "The game state changed.")

        return response_payload(202, {"message": "Game started"})

    except Exception as err:
        return internal_error_payload(err)
