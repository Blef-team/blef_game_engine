from shared.response import *
from shared.db import get_from_dynamodb
from shared.api_gateway import parse_event
from shared.inputs import is_valid_uuid
from shared.game import start_game

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

        admin_uuid = str(body.get("admin_uuid"))

        if not admin_uuid:
            return parameter_error_payload("admin_uuid", admin_uuid, message="Admin UUID missing - please supply it")

        if not is_valid_uuid(admin_uuid):
            return parameter_error_payload("admin_uuid", admin_uuid, message="Invalid admin UUID")

        players = game.get("players")
        game_admin_uuid = [player["uuid"] for player in players if player["nickname"] == game.get("admin_nickname")][0]
        if game_admin_uuid != admin_uuid:
            return parameter_error_payload("admin_uuid", admin_uuid, message="Admin UUID does not match")

        n_players = len(game.get("players", []))
        if n_players < 2:
            return error_payload(403, "At least 2 players needed to start a game")

        if  int(game.get("rules", {}).get("time_limit", 0)) > 0:
            return error_payload(403, "Games with a time limit can only start when everyone is ready")

        start_game(game)

        return response_payload(202, {"message": "Game started"})

    except Exception as err:
        return internal_error_payload(err)
