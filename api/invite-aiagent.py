import os
import json
import uuid
import logging

# Shared utilities using the new import style
from shared import response, input, db, game

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Load agent mapping from environment variable - essential for this function
try:
    # Ensure AGENT_MAPPING is loaded correctly
    agent_mapping_str = os.environ.get("AGENT_MAPPING")
    if not agent_mapping_str:
         logger.error("AGENT_MAPPING environment variable is not set or empty.")
         raise EnvironmentError("AGENT_MAPPING not configured")
    AGENT_MAPPING = json.loads(agent_mapping_str)
except (json.JSONDecodeError, EnvironmentError) as e:
     logger.critical(f"Failed to load AGENT_MAPPING: {e}")
     # Prevent lambda cold start without proper config
     raise


def lambda_handler(event, context):
    logger.info("Received request to invite AI agent.")
    params = None
    try:
        # 1. Parse Input
        params = input.parse_api_gateway_event(event)
        if not params:
            return response.bad_request_response(str(event))

        game_uuid = params.get("game_uuid")
        admin_uuid = params.get("admin_uuid")
        agent_name = params.get("agent_name") # User-friendly name like 'SimpleAgent'

        # 2. Validate Inputs
        if not input.is_valid_uuid(game_uuid):
            return response.bad_parameter_response("game_uuid", game_uuid, "Invalid game UUID format")
        if not admin_uuid:
             return response.bad_parameter_response("admin_uuid", admin_uuid, "Admin UUID missing")
        if not input.is_valid_uuid(admin_uuid):
            return response.bad_parameter_response("admin_uuid", admin_uuid, "Invalid admin UUID format")
        if not agent_name:
             return response.bad_parameter_response("agent_name", agent_name, "Agent name missing")

        # 3. Fetch Game Data
        game_data = db.get_game_from_db(game_uuid)
        if not game_data:
            return response.error_response("Game not found", status_code=404)

        # 4. Authorization & Preconditions
        if game_data.get("status") != "Not started":
            return response.error_response("Cannot invite agent: Game has already started", status_code=403)

        players = game_data.get("players", [])
        admin_player = game.get_player_by_nickname(players, game_data.get("admin_nickname"))

        if not admin_player or admin_player.get("uuid") != admin_uuid:
             logger.warning(f"Admin UUID mismatch or admin not found for game {game_uuid}. Request UUID: {admin_uuid}")
             return response.error_response("Provided admin UUID does not match the game admin", status_code=403)

        if len(players) >= 8:
            return response.error_response("Cannot invite agent: Game room is full", status_code=403)

        agent_type = AGENT_MAPPING.get(agent_name)
        if not agent_type:
             logger.warning(f"Invalid agent_name '{agent_name}' requested for game {game_uuid}.")
             return response.bad_parameter_response("agent_name", agent_name, f"Invalid agent name. Available: {list(AGENT_MAPPING.keys())}")

        # 5. Perform Action: Add AI Player
        existing_nicknames = [p.get("nickname") for p in players if p.get("nickname")]
        ai_nickname = game.format_ai_nickname(agent_name, existing_nicknames)
        ai_player_uuid = str(uuid.uuid4())

        ai_player = {
            "uuid": ai_player_uuid,
            "nickname": ai_nickname,
            "n_cards": 0,
            "ai_agent": agent_type
        }
        players.append(ai_player)
        logger.info(f"Prepared AI player: {ai_player}")

        # 6. Update Game State in DB
        success = db.update_game_players(game_uuid, players)

        if success:
            logger.info(f"Successfully added AI player {ai_nickname} to game {game_uuid}.")
            return response.success_response({"message": f"AI agent '{ai_nickname}' joined the game."})
        else:
            logger.error(f"Failed to update game {game_uuid} with new AI player.")
            raise RuntimeError("Failed to update game state in database")

    except Exception as e:
        game_id_log = params.get('game_uuid') if params else 'unknown'
        logger.exception(f"Error inviting AI agent for game {game_id_log}")
        return response.internal_error_response(e)
