import logging

# Shared utilities using the new import style
from shared import response, input, db, game

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    params = None # Define params for logging in except block
    try:
        logger.info(f"Received get_game request: {event.get('pathParameters')}, {event.get('queryStringParameters')}")
        # 1. Parse Input
        params = input.parse_api_gateway_event(event)
        if not params:
            logger.error(f"Failed to parse event: {event}")
            return response.bad_request_response(str(event))

        game_uuid = params.get("game_uuid")
        player_uuid = params.get("player_uuid")
        # round_param = params.get("round") # Add round logic if needed

        # 2. Validate Inputs
        if not input.is_valid_uuid(game_uuid):
            return response.bad_parameter_response("game_uuid", game_uuid, "Invalid game UUID format")
        if player_uuid and not input.is_valid_uuid(player_uuid):
            return response.bad_parameter_response("player_uuid", player_uuid, "Invalid player UUID format")

        # 3. Fetch Game Data
        # TODO: Add logic for historical round fetching if round_param is used
        game_data = db.get_game_from_db(game_uuid)
        if not game_data:
            logger.warning(f"Game not found for UUID: {game_uuid}")
            return response.error_response("Game not found", status_code=404)

        # 4. Authorize (Check if provided player_uuid belongs to this game)
        if player_uuid and not game.get_player_by_uuid(game_data.get("players", []), player_uuid):
             logger.warning(f"Player UUID {player_uuid} not found in game {game_uuid}.")
             return response.error_response("Player UUID does not match any player in this game", status_code=403)

        # 5. Censor Game State for Response
        visible_game = game.censor_game_state(game_data, player_uuid)
        if not visible_game:
             logger.error(f"Failed to censor game state for game {game_uuid}")
             raise RuntimeError("Failed to censor game state")

        logger.info(f"Successfully retrieved and censored game state for {game_uuid}")
        # 6. Return Response
        return response.success_response(visible_game)

    except Exception as e:
        game_id_log = params.get('game_uuid') if params else 'unknown'
        logger.exception(f"Error processing get_game request for UUID {game_id_log}")
        return response.internal_error_response(e)
