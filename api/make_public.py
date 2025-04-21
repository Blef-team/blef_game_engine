import logging

# Shared utilities using the new import style
from shared import response, input, db, game

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info("Received request to make game public.")
    params = None
    try:
        # 1. Parse Input
        params = input.parse_api_gateway_event(event)
        if not params:
            return response.bad_request_response(str(event))

        game_uuid = params.get("game_uuid")
        admin_uuid = params.get("admin_uuid")

        # 2. Validate Inputs
        if not input.is_valid_uuid(game_uuid):
            return response.bad_parameter_response("game_uuid", game_uuid, "Invalid game UUID format")
        if not admin_uuid:
             return response.bad_parameter_response("admin_uuid", admin_uuid, "Admin UUID missing")
        if not input.is_valid_uuid(admin_uuid):
            return response.bad_parameter_response("admin_uuid", admin_uuid, "Invalid admin UUID format")

        # 3. Fetch Game Data
        game_data = db.get_game_from_db(game_uuid)
        if not game_data:
            return response.error_response("Game not found", status_code=404)

        # 4. Authorization & Preconditions
        if game_data.get("status") != "Not started":
            return response.error_response("Cannot change setting: Game has already started", status_code=403)

        players = game_data.get("players", [])
        admin_player = game.get_player_by_nickname(players, game_data.get("admin_nickname"))

        if not admin_player or admin_player.get("uuid") != admin_uuid:
             logger.warning(f"Admin UUID mismatch for make_public request. Game: {game_uuid}, Request UUID: {admin_uuid}")
             return response.error_response("Provided admin UUID does not match the game admin", status_code=403)

        if game_data.get("public") == "true":
             logger.info(f"Game {game_uuid} is already public. No action needed.")
             return response.success_response({"message": "Game is already public"})

        # 5. Perform Action: Update public status
        logger.info(f"Setting game {game_uuid} to public.")
        success = db.update_game_public_status(game_uuid, is_public=True)

        # 6. Return Response
        if success:
            logger.info(f"Successfully set game {game_uuid} to public.")
            return response.success_response({"message": "Game successfully set to public"})
        else:
            logger.error(f"Failed to update game {game_uuid} to public.")
            raise RuntimeError("Failed to update game status in database")

    except Exception as e:
        game_id_log = params.get('game_uuid') if params else 'unknown'
        logger.exception(f"Error making game public for game {game_id_log}")
        return response.internal_error_response(e)
