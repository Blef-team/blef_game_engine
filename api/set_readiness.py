import time
import decimal
from shared.response import response_payload, parameter_error_payload, error_payload, internal_error_payload
from shared.db import table
from shared.constants import GameStatus
from shared.game import update_n_cards, start_game, start_next_round, get_action_ids
from shared.decorators import validate_game_request

def update_player_readiness(game_uuid, player_index, ready_status):
    """
    Atomically updates a single player's readiness and returns the full, updated game state.
    """
    response = table.update_item(
        Key={'game_uuid': game_uuid},
        UpdateExpression=f"SET players[{player_index}].ready = :ready, last_modified = :last_modified",
        ExpressionAttributeValues={
            ':ready': ready_status,
            ':last_modified': decimal.Decimal(str(time.time()))
        },
        ReturnValues="ALL_NEW"
    )
    return response.get('Attributes')

@validate_game_request(require_player=True)
def lambda_handler(event, context, body, game):
    try:
        ready = body.get("ready")
        if ready not in ['True', 'False']:
            return parameter_error_payload("ready", ready, message="Ready must be a boolean")
        ready = True if ready == 'True' else False

        # Decorator guarantees the player exists in the game
        player_uuid = str(body.get("player_uuid"))
        players = game.get("players", [])
        player_index = next(i for i, p in enumerate(players) if p["uuid"] == player_uuid)

        if len(players) < 2:
            return error_payload(403, "Cannot set readiness with only one player in the room.")

        updated_game_state = update_player_readiness(game["game_uuid"], player_index, ready)

        game_status = updated_game_state.get("status")
        if game_status == GameStatus.WAITING_FOR_READY:
            action_ids = get_action_ids(updated_game_state.get("rules", {}))
            losing_player_nickname = next((event.get("player") for event in reversed(updated_game_state.get("history", [])) if event.get("action_id") == action_ids["lose_round"]), None)
            temp_players = update_n_cards(updated_game_state, losing_player_nickname)
            active_players_for_next_round = [p for p in temp_players if p.get("n_cards", 0) > 0]
            
            if len(active_players_for_next_round) >= 2 and all(p.get("ready") for p in active_players_for_next_round):
                start_next_round(updated_game_state)
                return response_payload(200, {"message": "All players ready. Next round started."})
                
        elif game_status == GameStatus.NOT_STARTED:
            updated_players = updated_game_state.get("players", [])
            all_ready = all(p.get("ready", False) for p in updated_players)
            has_enough_players = (len(updated_players) >= 2)
            non_null_teams = [t for t in [p.get("team") for p in updated_players] if t is not None]
            is_single_team = (len(non_null_teams) == len(updated_players) and len(set(non_null_teams)) == 1)
            
            if all_ready and has_enough_players and not is_single_team:
                start_game(updated_game_state)
                return response_payload(200, {"message": "All players ready. Game started."})
                
        return response_payload(200, {"message": "Readiness updated"})

    except Exception as err:
        return internal_error_payload(err)
