import logging

# Shared utilities using the new import style
from shared import response, db, game

logger = logging.getLogger()
logger.setLevel(logging.INFO)

MAX_GAME_AGE_SECONDS = 600 # 10 minutes

def lambda_handler(event, context):
    logger.info("Starting clean_public_games task.")
    cleaned_game_uuids = []
    errors = []

    try:
        # Use db module
        public_games_metadata = db.get_public_games_for_cleanup()
        logger.info(f"Found {len(public_games_metadata)} public games to check.")

        for game_meta in public_games_metadata:
            game_uuid = game_meta.get("game_uuid")
            if not game_uuid:
                logger.warning(f"Found public game entry with missing UUID: {game_meta}")
                continue

            # Use game module for logic
            if game.is_game_too_old(game_meta, MAX_GAME_AGE_SECONDS):
                logger.info(f"Game {game_uuid} is older than {MAX_GAME_AGE_SECONDS} seconds. Setting to private.")
                try:
                    # Use db module
                    success = db.update_game_public_status(game_uuid, is_public=False)
                    if success:
                        cleaned_game_uuids.append(game_uuid)
                        logger.info(f"Successfully set game {game_uuid} to private.")
                    else:
                        logger.error(f"Failed to set game {game_uuid} to private (update returned false).")
                        errors.append(f"Failed to update {game_uuid}")
                except Exception as update_err:
                    logger.exception(f"Error updating game {game_uuid} to private.")
                    errors.append(f"Error updating {game_uuid}: {update_err}")

        logger.info(f"Clean-up task finished. Set {len(cleaned_game_uuids)} games to private.")
        if errors:
             logger.warning(f"Encountered errors during cleanup: {errors}")

        # Use response module
        return response.success_response(cleaned_game_uuids)

    except Exception as e:
        logger.exception("Fatal error during clean_public_games task.")
        # Use response module
        return response.internal_error_response(e, "Error during game cleanup")
