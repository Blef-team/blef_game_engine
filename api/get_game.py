from shared.response import response_payload, parameter_error_payload, internal_error_payload
from shared.db import get_from_dynamodb
from shared.constants import GameStatus
from shared.game import get_nickname_by_uuid, censor_game
from shared.inputs import is_valid_uuid
from shared.decorators import validate_game_request


@validate_game_request()
def lambda_handler(event, context, body, game):
    try:
        current_status = game.get("status")
        player_uuid = body.get("player_uuid")

        # Optional player authentication for viewing private hand data
        if player_uuid and not is_valid_uuid(player_uuid):
            return parameter_error_payload("player_uuid", player_uuid, message="Invalid player UUID")

        round_param = body.get("round")

        if round_param:
            if isinstance(round_param, str) and round_param.isdigit():
                round_param = int(round_param)
            elif not isinstance(round_param, int):
                return parameter_error_payload("round", round_param)

        if round_param and round_param <= 0:
            return parameter_error_payload("round", round_param, message="The round parameter is invalid - must be an integer between 1 and the current round, or -1, or blank")
        
        current_round = game["round_number"]
        if round_param and current_round < round_param:
            return parameter_error_payload("round", round_param, message="The game has not reached this round")

        # Fetch historical round if requested
        if round_param and (round_param != current_round or current_status != GameStatus.RUNNING):
            game = get_from_dynamodb(f"{game['game_uuid']}_{round_param}")
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
