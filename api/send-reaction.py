import logging
import os

# Shared utilities using the new import style
from shared import response, input, db, game, sqs

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REACTION_QUEUE_NAME = os.environ.get("REACTION_QUEUE_NAME")
if not REACTION_QUEUE_NAME:
     logger.critical("REACTION_QUEUE_NAME environment variable not set.")
     raise EnvironmentError("REACTION_QUEUE_NAME not configured")

def lambda_handler(event, context):
    logger.info("Received request to send reaction.")
    params = None
    try:
        # 1. Parse Input
        params = input.parse_api_gateway_event(event)
        if not params:
            return response.bad_request_response(str(event))

        game_uuid = params.get("game_uuid")
        player_uuid = params.get("player_uuid")
        nickname = params.get("nickname")
        reaction = params.get("reaction")

        # 2. Validate Inputs
        # Use input module
        if not input.is_valid_uuid(game_uuid):
            return response.bad_parameter_response("game_uuid", game_uuid, "Invalid game UUID format")
        if not nickname:
            return response.bad_parameter_response("nickname", nickname, "Nickname missing")
        if not reaction:
             return response.bad_parameter_response("reaction", reaction, "Reaction missing")
        if not input.is_valid_reaction(reaction):
            return response.bad_parameter_response("reaction", reaction, "Invalid reaction format or content")
        if player_uuid and not input.is_valid_uuid(player_uuid):
             return response.bad_parameter_response("player_uuid", player_uuid, "Invalid player UUID format")

        # 3. Fetch Game Data (for validation)
        game_data = db.get_game_from_db(game_uuid)
        if not game_data:
            return response.error_response("Game not found", status_code=404)

        # 4. Authenticate Nickname (Optional)
        nickname_authenticated = "false"
        is_actual_player = False
        if player_uuid:
            # Use game module
            actual_nickname = game.get_nickname_by_uuid(game_data.get("players", []), player_uuid)
            if actual_nickname:
                 is_actual_player = True
                 if actual_nickname == nickname:
                      nickname_authenticated = "true"
                 else:
                      logger.warning(f"Nickname mismatch for reaction. UUID {player_uuid} ({actual_nickname}) sent reaction as '{nickname}'")

        # 5. Construct and Send Message to SQS
        reaction_message = {
            "type": "reaction",
            "game_uuid": game_uuid,
            "nickname": nickname,
            "reaction": reaction,
            "nickname_authenticated": nickname_authenticated,
            "is_player": is_actual_player
        }
        logger.info(f"Sending reaction message to SQS: {reaction_message}")

        # Use sqs module
        success = sqs.send_sqs_message(REACTION_QUEUE_NAME, reaction_message)

        # 6. Return Response
        if success:
            logger.info(f"Reaction from '{nickname}' for game {game_uuid} queued successfully.")
            return response.success_response({"message": "Reaction received"})
        else:
            logger.error(f"Failed to queue reaction from '{nickname}' for game {game_uuid}.")
            raise RuntimeError("Failed to send reaction message to queue")

    except Exception as e:
        game_id_log = params.get('game_uuid') if params else 'unknown'
        logger.exception(f"Error processing send-reaction for game {game_id_log}")
        return response.internal_error_response(e)
