from shared.response import response_payload, error_payload, internal_error_payload
from shared.db import update_players_conditionally
from shared.constants import GameStatus
from shared.game import calculate_actual_max_cards
from shared.decorators import validate_game_request

@validate_game_request(
    require_admin=True, 
    required_status=GameStatus.NOT_STARTED, 
    status_error_message="Cannot remove AIs after the game has started"
)
def lambda_handler(event, context, body, game):
    try:
        players = game.get("players", [])
        human_players = [p for p in players if not p.get("ai_agent")]

        if len(human_players) == len(players):
            return response_payload(200, {"message": "No AI players to remove."})
        
        max_cards = calculate_actual_max_cards(game.get("rules", {}), len(human_players))

        if not update_players_conditionally(game["game_uuid"], human_players, game["last_modified"], max_cards=max_cards):
            return error_payload(409, "The game state changed. Please try again.")

        return response_payload(200, {"message": "All AI players have been removed."})

    except Exception as err:
        return internal_error_payload(err)
