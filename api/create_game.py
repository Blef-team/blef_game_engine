import uuid
import random
import re
from shared.response import * 
from shared.db import save_in_dynamodb
from shared.api_gateway import parse_event


def lambda_handler(event, context):
    try:
        body = parse_event(event)
        if not body:
            return request_error_payload(event)

        game_uuid = str(uuid.uuid4())
        game = {
            "game_uuid": game_uuid,
            "admin_nickname": None,
            "public": "false",
            "room": random.randrange(10, 100),
            "status": "Not started",
            "round_number": 0,
            "max_cards": 0,
            "players": [],
            "hands": [],
            "cp_nickname": None,
            "history": []
        }

        nickname = body.get("nickname")
        if not nickname and save_in_dynamodb(game):
                return response_payload(200, {"game_uuid": game_uuid})

        if not isinstance(nickname, str):
            return parameter_error_payload("nickname", nickname, message="Nickname invalid")
        if not re.match("^[a-zA-Z]\w*$", nickname):
            return parameter_error_payload("nickname", nickname, message="Nickname must start with a letter and only contain alphanumeric characters")
        player_uuid = str(uuid.uuid4())
        player = {"uuid": player_uuid, "nickname": nickname, "n_cards": 0}
        game.update({"players": [player], "admin_nickname": nickname})
        if save_in_dynamodb(game):
            return response_payload(200, {"game_uuid": game_uuid, "player_uuid": player_uuid})

        raise(Exception("Something went wrong - ended up with no response"))

    except Exception as err:
        return internal_error_payload(err)
