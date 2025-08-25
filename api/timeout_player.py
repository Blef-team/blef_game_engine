import json
from shared.response import *
from shared.constants import GameStatus
from shared.db import get_from_dynamodb
from shared.game import get_nickname_by_uuid, end_round

def lambda_handler(event, context):
    try:
        for record in event['Records']:
            body = json.loads(record['body'])
            game_uuid = body.get("game_uuid")
            player_uuid = body.get("player_uuid")
            round_number = body.get("round_number")
            history_len_at_send = body.get("history_len")

            game = get_from_dynamodb(game_uuid)
            
            # Ignore if game is not in the correct state
            if not game or game.get("status") != GameStatus.RUNNING or game.get("round_number") != round_number:
                continue
            
            player_nickname = get_nickname_by_uuid(game["players"], player_uuid)
            
            current_history_len = len(game.get("history", []))
            if game.get("cp_nickname") == player_nickname and current_history_len == history_len_at_send:
                end_round(game, player_nickname)

        return response_payload(200, {"message": "Timeouts processed"})

    except Exception as err:
        return internal_error_payload(err)
