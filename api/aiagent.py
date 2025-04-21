import logging
import json # Keep for logging if needed

# Local agent logic (adjust path if needed)
# Assuming agent.py is specific to this lambda or also refactored
# If agent is also shared, use: from shared import agent
import agent

# Shared utilities using the new import style
from shared import response, input, game, lambda_invoker

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info('## EVENT')
    logger.info(event)

    try:
        # Use input module for parsing
        game_data = input.parse_api_gateway_event(event)
        if not game_data:
             if isinstance(event, dict) and 'game_uuid' in event:
                 game_data = event # Handle direct invoke
                 logger.info("Handling direct invoke event.")
             else:
                 logger.error("Could not parse game data from event.")
                 raise ValueError("Could not parse game data")

        logger.info('## GAME DATA')
        logger.info(game_data)

        # Validate game data structure minimally
        if not all(k in game_data for k in ('game_uuid', 'cp_nickname', 'players', 'history')):
             logger.error("Game data missing required keys.")
             raise ValueError("Game data missing required keys")

        # Use game module for game logic
        aiagent_player_uuid = game.get_aiagent_player_uuid(game_data)
        if not aiagent_player_uuid:
            logger.error("Could not determine AI agent player UUID for current player.")
            # Use response module for formatting
            return response.success_response({"message": "Current player is not this AI agent or UUID not found."})

        # Determine action using the specific agent's logic
        action = agent.determine_action(game_data)
        logger.info(f'## Determined Action: {action}')

        # Use game module for validation
        if not game.is_legal_action(action, game_data.get("history", [])):
            logger.error(f"Determined action {action} is illegal.")
            raise ValueError(f"Agent generated illegal action: {action}")

        # Use lambda_invoker module
        success = lambda_invoker.call_play_lambda(
            action_id=action,
            player_uuid=aiagent_player_uuid, # Renamed for clarity
            game_uuid=game_data["game_uuid"]
        )

        if success:
            message = f"Action {action} initiated for game {game_data['game_uuid']}"
            logger.info(message)
            # Use response module
            return response.success_response({"message": message})
        else:
            message = f"Failed to invoke play lambda for action {action} in game {game_data['game_uuid']}"
            logger.error(message)
            raise RuntimeError(message)

    except Exception as e:
        logger.exception("Error in AI Agent Lambda")
        # Use response module for internal errors if it's an API call
        # return response.internal_error_response(e)
        # Re-raise for async triggers (like SQS)
        raise
