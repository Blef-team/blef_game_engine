import logging
import os
import json

# Shared utilities using the new import style
from shared import response, input, db, game, sqs, websocket

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AIAGENT_QUEUE_NAME = os.environ.get("AIAGENT_QUEUE_NAME")
if not AIAGENT_QUEUE_NAME:
     logger.critical("AIAGENT_QUEUE_NAME environment variable not set.")
     raise EnvironmentError("AIAGENT_QUEUE_NAME not configured")

def process_record(record):
    """ Processes a single DynamoDB stream record. """
    event_name = record.get('eventName')
    logger.info(f"Processing DynamoDB Stream record. EventName: {event_name}")

    dynamodb_data = record.get('dynamodb', {})
    new_image_raw = dynamodb_data.get('NewImage')
    old_image_raw = dynamodb_data.get('OldImage')

    # Use db module
    game_new = db.deserialise_dynamodb_stream_event(new_image_raw) if new_image_raw else {}
    game_old = db.deserialise_dynamodb_stream_event(old_image_raw) if old_image_raw else {}

    game_uuid = (game_new or game_old).get('game_uuid', 'Unknown UUID')
    logger.info(f"Record relates to game: {game_uuid} (Event: {event_name})")

    current_game_state = game_new if event_name in ('INSERT', 'MODIFY') else None

    if current_game_state:
        # Use websocket module
        websocket.broadcast_game_state(current_game_state)

        is_public_now = current_game_state.get("public") == "true"
        was_public_before = game_old.get("public") == "true"
        if is_public_now or was_public_before:
             # Use websocket module
             websocket.broadcast_public_game_update(current_game_state)
        # Handle REMOVE case if needed
    else:
         logger.info(f"No current game state found for event {event_name} on game {game_uuid}. Skipping watcher updates.")

    if event_name == 'MODIFY':
        cp_new = game_new.get('cp_nickname')
        cp_old = game_old.get('cp_nickname')
        status_new = game_new.get('status')

        if status_new == 'Running' and cp_new != cp_old and cp_new is not None:
            logger.info(f"Current player changed to {cp_new} in game {game_uuid}.")
            # Use game module
            player = game.get_player_by_nickname(game_new.get("players", []), cp_new)
            if player and player.get("ai_agent"):
                 logger.info(f"New player {cp_new} is AI ({player.get('ai_agent')}). Queueing AI agent.")
                 # Use sqs module
                 success = sqs.send_sqs_message(
                     AIAGENT_QUEUE_NAME, game_new, message_group_id=game_uuid
                 )
                 if not success:
                      logger.error(f"Failed to queue AI agent message for game {game_uuid}, player {cp_new}.")
            else:
                 logger.info(f"New player {cp_new} is not an AI or not found.")

def lambda_handler(event, context):
    logger.info(f"Received {len(event.get('Records', []))} DynamoDB stream records.")
    errors = []

    for record in event.get('Records', []):
        try:
            process_record(record)
        except Exception as e:
            record_id = record.get('eventID', 'Unknown Record')
            logger.exception(f"Error processing DynamoDB Stream record {record_id}")
            errors.append(record_id)

    if errors:
        logger.error(f"Finished processing stream with {len(errors)} errors for records: {errors}")

    logger.info("DynamoDB stream processing complete.")
    # Use response module (although return value isn't used by DDB Streams)
    return response.format_response(200, {"message": f"Processed stream records. Errors: {len(errors)}"})
