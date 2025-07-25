import time
import decimal
import copy
from shared.response import *
from shared.db import table, get_from_dynamodb
from shared.api_gateway import parse_event
from shared.inputs import is_valid_uuid
from shared.game import start_game, start_next_round, get_player_by_nickname, get_action_ids

def update_in_dynamodb(game_uuid, players):
    table.update_item(
        Key={
            'game_uuid': game_uuid
        },
        UpdateExpression="set players = :players, last_modified = :last_modified",
        ExpressionAttributeValues={
            ':players': players,
            ':last_modified': decimal.Decimal(str(time.time()))
        },
        ReturnValues="NONE"
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

        player_uuid = str(body.get("player_uuid"))
        if not is_valid_uuid(player_uuid):
            return parameter_error_payload("player_uuid", player_uuid, message="Invalid player UUID")

        ready = body.get("ready")
        if ready == 'True':
            ready = True
        elif ready == 'False':
            ready = False
        else:
            return parameter_error_payload("ready", ready, message="Ready must be a boolean")

        players = game.get("players")
        player_found = False
        for player in players:
            if player["uuid"] == player_uuid:
                player["ready"] = ready
                player_found = True
                break

        if not player_found:
            return parameter_error_payload("player_uuid", player_uuid, message="Player not found in this game")

        game_status = game.get("status")
        
        if game_status == "Waiting for ready":
            temp_players = copy.deepcopy(players)
            action_ids = get_action_ids(game.get("rules", {}))
            losing_player_nickname = None
            for event in reversed(game.get("history", [])):
                if event.get("action_id") == action_ids["lose_round"]:
                    losing_player_nickname = event.get("player")
                    break
            losing_player = get_player_by_nickname(temp_players, losing_player_nickname)
            if losing_player:
                losing_player["n_cards"] += 1
                if losing_player["n_cards"] > game["max_cards"]:
                    losing_player["n_cards"] = 0
            active_players_for_next_round = [p for p in temp_players if p.get("n_cards", 0) > 0]
        elif game_status == "Not started":
            active_players_for_next_round = players

        all_active_players_ready = len(active_players_for_next_round) >= 2 and all(p.get("ready") for p in active_players_for_next_round)

        if all_active_players_ready:
            if game_status == "Not started":
                start_game(game)
                return response_payload(200, {"message": "All players ready. Game started."})
            elif game_status == "Waiting for ready":
                start_next_round(game)
                return response_payload(200, {"message": "All players ready. Next round started."})
        else:
            update_in_dynamodb(game_uuid, players)

        return response_payload(200, {"message": "Readiness updated"})

    except Exception as err:
        return internal_error_payload(err)
