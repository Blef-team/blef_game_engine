import logging
import json

# Shared utilities using the new import style
from shared import game, lambda_invoker, sqs

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info('## SQS EVENT')
    logger.info(event)
    processed_messages = 0
    failed_messages = 0

    # Assuming SQS trigger, iterate through records
    for record in event.get('Records', []):
        logger.info(f"Processing SQS record: {record.get('messageId')}")

        try:
            # Use sqs module to extract message body
            game_data = sqs.extract_game_from_sqs_record(record)
            if not game_data:
                logger.warning(f"Could not extract game from record {record.get('messageId')}, skipping.")
                failed_messages += 1
                continue

            logger.info(f"## Extracted Game (UUID: {game_data.get('game_uuid')})")

            # Use game module for logic
            agent_type = game.get_aiagent_type(game_data)
            if not agent_type:
                logger.info(f"No AI agent type found for current player '{game_data.get('cp_nickname')}' in game {game_data.get('game_uuid')}. Skipping invocation.")
                processed_messages += 1
                continue

            logger.info(f"Current player '{game_data.get('cp_nickname')}' is AI type: {agent_type}. Invoking agent lambda.")

            # Use lambda_invoker module
            success = lambda_invoker.call_ai_agent_lambda(agent_type, game_data)

            if success:
                logger.info(f"Successfully invoked agent '{agent_type}' for game {game_data.get('game_uuid')}")
                processed_messages += 1
            else:
                logger.error(f"Failed to invoke agent '{agent_type}' for game {game_data.get('game_uuid')}")
                failed_messages += 1

        except Exception as e:
            logger.exception(f"Error processing SQS record {record.get('messageId')}")
            failed_messages += 1

    logger.info(f"Processing complete. Success: {processed_messages}, Failed: {failed_messages}")

    # Return simple response for SQS trigger
    return {
        'statusCode': 200,
        'body': json.dumps({"message": f"Processed {processed_messages} messages, {failed_messages} failures."})
    }
