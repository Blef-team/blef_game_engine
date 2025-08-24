from shared.response import *
from shared.db import get_from_dynamodb
from shared.api_gateway import parse_event
from shared.constants import GameStatus
from shared.game import get_nickname_by_uuid, censor_game
from shared.inputs import is_valid_uuid


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

        current_status = game.get("status")

        player_uuid = body.get("player_uuid")

        if player_uuid and not is_valid_uuid(player_uuid):
            return parameter_error_payload("player_uuid", player_uuid, message="Invalid player UUID")

        round_param = body.get("round")

        if round_param:
            if isinstance(round_param, str) and round_param.isdigit():
                round_param = int(round_param)
            elif isinstance(round_param, int):
                pass
            else:
                return parameter_error_payload("round", round_param)

        if round_param and round_param <= 0:
            return parameter_error_payload("round", round_param, message="The round parameter is invalid - must be an integer between 1 and the current round, or -1, or blank")
        current_round = game["round_number"]
        if round_param and current_round < round_param:
            return parameter_error_payload("round", round_param, message="The game has not reached this round")

        if round_param and (round_param != current_round or current_status != GameStatus.RUNNING):
            game = get_from_dynamodb(f"{game_uuid}_{round_param}")
        else:
            round_param = current_round

        player_nickname = None
        if player_uuid:
            player_nickname = get_nickname_by_uuid(game["players"], player_uuid)
            if not player_nickname:
                return parameter_error_payload("player_uuid", player_uuid, message="The UUID does not match any active player")

        visible_game = censor_game(game, player_nickname)

        return response_payload(200, visible_game)

    except Exception as err:
        return internal_error_payload(err)
