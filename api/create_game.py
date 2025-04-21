import uuid
import random
import logging

# Shared utilities using the new import style
from shared import response, db

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info("Received request to create game.")
    try:
        game_uuid = str(uuid.uuid4())
        room_number = random.randrange(1000, 9999)

        empty_game = {
            "game_uuid": game_uuid,
            "admin_nickname": None,
            "public": "false",
            "room": room_number,
            "status": "Not started",
            "round_number": 0,
            "max_cards": 0,
            "players": [],
            "hands": [],
            "cp_nickname": None,
            "history": []
        }
        logger.info(f"Generated new game template with UUID: {game_uuid}, Room: {room_number}")

        # Use db module
        success = db.save_game_to_db(empty_game)

        if success:
            logger.info(f"Successfully saved new game {game_uuid} to DynamoDB.")
            # Use response module
            return response.success_response({"game_uuid": game_uuid})
        else:
             logger.error(f"Failed to save game {game_uuid} (save returned false).")
             raise RuntimeError("Failed to save game to database")

    except Exception as e:
        logger.exception("Error creating game.")
        # Use response module
        return response.internal_error_response(e, "Error creating new game")
