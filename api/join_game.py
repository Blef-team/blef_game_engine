import uuid
import time
import re
import decimal
from shared.response import *
from shared.db import table, get_from_dynamodb
from shared.api_gateway import parse_event
from shared.inputs import is_valid_uuid


def update_in_dynamodb(game_uuid, players, admin_nickname):
    # # Unset readiness for all human players after any join - too annoying for now when people mostly play with friends or try to learn the game
    # players = unset_human_readiness(players)

    table.update_item(
        Key={
            'game_uuid': game_uuid
        },
        UpdateExpression="set players = :players, last_modified = :last_modified, admin_nickname = :admin_nickname",
        ExpressionAttributeValues={
            ':players': players,
            ':last_modified': decimal.Decimal(str(time.time())),
            ':admin_nickname': admin_nickname
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

        if game.get("status") != "Not started":
            return error_payload(403, "Game already started")

        if len(game.get("players")) == 8:
            return error_payload(403, "Game room full")

        nickname = body.get("nickname")
        if not nickname:
            return parameter_error_payload("nickname", nickname, message="Nickname missing - please supply it")
        if not isinstance(nickname, str):
            return parameter_error_payload("nickname", nickname, message="Nickname invalid")
        if not re.match("^[a-zA-Z]\w*$", nickname):
            return parameter_error_payload("nickname", nickname, message="Nickname must start with a letter and only contain alphanumeric characters")

        players = game.get("players")
        if nickname in [p["nickname"] for p in players]:
            return parameter_error_payload("nickname", nickname, message="Nickname already taken")

        player_uuid = str(uuid.uuid4())
        player = {"uuid": player_uuid, "nickname": nickname, "n_cards": 0, "ready": False}
        players.append(player)

        admin_nickname = game.get("admin_nickname")
        if len(players) == 1:
            admin_nickname = nickname

        update_in_dynamodb(game_uuid, players, admin_nickname)

        response = {"player_uuid": player_uuid}
        return response_payload(200, response)

    except Exception as err:
        return internal_error_payload(err)
