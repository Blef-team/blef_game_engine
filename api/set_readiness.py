import time
import decimal
import copy
from shared.response import *
from shared.db import table, get_from_dynamodb
from shared.api_gateway import parse_event
from shared.constants import GameStatus
from shared.game import update_n_cards
from shared.inputs import is_valid_uuid
from shared.game import start_game, start_next_round, get_player_by_nickname, get_action_ids

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

        player_uuid = str(body.get("player_uuid"))
        if not is_valid_uuid(player_uuid):
            return parameter_error_payload("player_uuid", player_uuid, message="Invalid player UUID")

        ready = body.get("ready")
        if ready not in ['True', 'False']:
            return parameter_error_payload("ready", ready, message="Ready must be a boolean")
        ready = True if ready == 'True' else False

        players = game.get("players")
        player_index = -1
        for i, player in enumerate(players):
            if player["uuid"] == player_uuid:
                player_index = i
                break

        if player_index == -1:
            return parameter_error_payload("player_uuid", player_uuid, message="Player not found in this game")

        if len(game.get("players", [])) < 2:
            return error_payload(403, "Cannot set readiness with only one player in the room.")

        updated_game_state = update_player_readiness(game_uuid, player_index, ready)

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
            players = updated_game_state.get("players", [])
            all_ready = all(p.get("ready", False) for p in players)
            has_enough_players = (len(players) >= 2)
            non_null_teams = [t for t in [p.get("team") for p in players] if t is not None]
            is_single_team = (len(non_null_teams) == len(players) and len(set(non_null_teams)) == 1)
            if all_ready and has_enough_players and not is_single_team:
                start_game(updated_game_state)
                return response_payload(200, {"message": "All players ready. Game started."})
        return response_payload(200, {"message": "Readiness updated"}) # Shouldn't be reached

    except Exception as err:
        return internal_error_payload(err)
