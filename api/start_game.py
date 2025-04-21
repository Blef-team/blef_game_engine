import logging
import decimal # Needed for constructing update values
from math import floor

# Shared utilities using the new import style
from shared import response, input, db, game

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info("Received request to start game.")
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
            return response.error_response("Game has already started or finished", status_code=403)

        players = game_data.get("players", [])
        # Use game module
        admin_player = game.get_player_by_nickname(players, game_data.get("admin_nickname"))

        if not admin_player or admin_player.get("uuid") != admin_uuid:
             logger.warning(f"Admin UUID mismatch for start_game request. Game: {game_uuid}, Request UUID: {admin_uuid}")
             return response.error_response("Provided admin UUID does not match the game admin", status_code=403)

        n_players = len(players)
        if n_players < 2:
            return response.error_response("At least 2 players are needed to start the game", status_code=400)

        # --- 5. Prepare Game Start State ---
        logger.info(f"Starting game {game_uuid} with {n_players} players.")
        # Use game module
        arranged_players = game.arrange_players(players)

        for player in arranged_players: player["n_cards"] = 1
        max_cards = 11 if n_players <= 2 else floor(24 / n_players)
        logger.info(f"Max cards per player set to: {max_cards}")

        # Use game module
        initial_hands = game.draw_cards(arranged_players)
        cp_nickname = arranged_players[0].get("nickname")
        if not cp_nickname: raise ValueError("Could not get nickname of starting player.")

        # --- 6. Update Game State in DB ---
        update_expression = "set #s = :s, round_number = :rn, max_cards = :mc, players = :p, hands = :h, cp_nickname = :cpn, #pub = :pub"
        expression_attribute_values = {
            ':s': "Running", ':rn': decimal.Decimal(1), ':mc': decimal.Decimal(max_cards),
            ':p': arranged_players, ':h': initial_hands, ':cpn': cp_nickname, ':pub': "false"
        }
        expression_attribute_names = { '#s': "status", '#pub': "public" }

        logger.info(f"Updating game state for {game_uuid} to start.")
        # Use db module
        success = db.update_game_in_db(
            game_uuid, update_expression, expression_attribute_values, expression_attribute_names
        )

        # 7. Return Response
        if success:
            logger.info(f"Game {game_uuid} started successfully.")
            return response.success_response({"message": "Game started"}, status_code=202)
        else:
            logger.error(f"Failed to update game state for {game_uuid} to start.")
            raise RuntimeError("Failed to update game state in database")

    except Exception as e:
        game_id_log = params.get('game_uuid') if params else 'unknown'
        logger.exception(f"Error starting game {game_id_log}")
        return response.internal_error_response(e)
