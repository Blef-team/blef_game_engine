import logging
import json

# Shared utilities using the new import style
from shared import sqs, websocket

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info('## SQS Reaction Event Received')
    processed_messages = 0
    failed_messages = 0

    for record in event.get('Records', []):
        message_id = record.get('messageId', 'Unknown')
        logger.info(f"Processing reaction message ID: {message_id}")
        try:
            # Use sqs module
            reaction_details = sqs.extract_reaction_from_sqs_record(record)

            if not reaction_details or not isinstance(reaction_details, dict):
                logger.error(f"Could not extract valid reaction details from SQS message {message_id}. Body: {record.get('body')}")
                failed_messages += 1
                continue

            if not all(k in reaction_details for k in ('game_uuid', 'nickname', 'reaction')):
                 logger.error(f"Reaction details missing required fields in message {message_id}. Details: {reaction_details}")
                 failed_messages += 1
                 continue

            logger.info(f"Broadcasting reaction: {reaction_details}")
            # Use websocket module
            websocket.broadcast_reaction(reaction_details)

            processed_messages += 1

        except Exception as e:
            logger.exception(f"Error processing reaction SQS message {message_id}")
            failed_messages += 1

    logger.info(f"Reaction broadcast processing complete. Success: {processed_messages}, Failed: {failed_messages}")

    # Return simple response for SQS trigger
    return {
        'statusCode': 200,
        'body': json.dumps({"message": f"Processed {processed_messages} reaction messages, {failed_messages} failures."})
    }
