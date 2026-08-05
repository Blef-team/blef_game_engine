import time
import decimal
from botocore.exceptions import ClientError
from shared.response import response_payload, parameter_error_payload, error_payload, conflict_payload, internal_error_payload
from shared.db import table, RACE_LOST_ERROR_CODES
from shared.constants import GameStatus
from shared.game import update_n_cards, start_game, start_next_round, find_losing_player_nickname
from shared.decorators import validate_game_request
from shared.websocket import broadcast_game_state
from shared.logging import logger

def update_player_readiness(game_uuid, player_index, player_uuid, ready_status):
    """
    Atomically updates a single player's readiness and returns the full, updated game
    state, or None if the roster shifted under us. Guarded on the slot still holding the
    player we resolved: a removal shifts every later index down, so an unguarded write
    would land on somebody else.
    """
    try:
        response = table.update_item(
            Key={'game_uuid': game_uuid},
            UpdateExpression=f"SET players[{player_index}].ready = :ready, last_modified = :last_modified",
            ConditionExpression=f"players[{player_index}].#uuid = :player_uuid",
            ExpressionAttributeNames={'#uuid': "uuid"},
            ExpressionAttributeValues={
                ':ready': ready_status,
                ':last_modified': decimal.Decimal(str(time.time())),
                ':player_uuid': player_uuid
            },
            ReturnValues="ALL_NEW"
        )
        return response.get('Attributes')
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code in RACE_LOST_ERROR_CODES:
            logger.warning(f"Readiness write for game {game_uuid} lost a race: {error_code}.")
            return None
        else:
            raise

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

        updated_game_state = update_player_readiness(game["game_uuid"], player_index, player_uuid, ready)
        if not updated_game_state:
            return conflict_payload()

        game_status = updated_game_state.get("status")
        if game_status == GameStatus.WAITING_FOR_READY:
            losing_player_nickname = find_losing_player_nickname(updated_game_state)
            temp_players = update_n_cards(updated_game_state, losing_player_nickname)
            active_players_for_next_round = [p for p in temp_players if p.get("n_cards", 0) > 0]

            # A start that loses its race leaves the game as it was; the readiness itself
            # still landed, so report that and let the winning write drive the start.
            if len(active_players_for_next_round) >= 2 and all(p.get("ready") for p in active_players_for_next_round):
                if start_next_round(updated_game_state):
                    broadcast_game_state(updated_game_state)
                    return response_payload(200, {"message": "All players ready. Next round started."})

        elif game_status == GameStatus.NOT_STARTED:
            updated_players = updated_game_state.get("players", [])
            all_ready = all(p.get("ready", False) for p in updated_players)
            has_enough_players = (len(updated_players) >= 2)
            non_null_teams = [t for t in [p.get("team") for p in updated_players] if t is not None]
            is_single_team = (len(non_null_teams) == len(updated_players) and len(set(non_null_teams)) == 1)

            if all_ready and has_enough_players and not is_single_team:
                if start_game(updated_game_state):
                    broadcast_game_state(updated_game_state)
                    return response_payload(200, {"message": "All players ready. Game started."})

        broadcast_game_state(updated_game_state)
        return response_payload(200, {"message": "Readiness updated"})

    except Exception as err:
        return internal_error_payload(err)
