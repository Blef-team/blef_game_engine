import boto3
import json
import logging
import os
from botocore.exceptions import ClientError
from shared.db import DecimalEncoder # Import from renamed db module

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sqs_client = boto3.client("sqs")
_queue_url_cache = {} # Cache for queue URLs

def get_queue_url(queue_name):
    """ Gets and caches the SQS queue URL for a given queue name. """
    if not queue_name: # Check if queue_name is provided
         logger.error("SQS queue name must be provided.")
         return None
    if queue_name in _queue_url_cache:
        return _queue_url_cache[queue_name]

    try:
        response = sqs_client.get_queue_url(QueueName=queue_name)
        url = response['QueueUrl']
        _queue_url_cache[queue_name] = url
        logger.info(f"Resolved SQS queue URL for '{queue_name}': {url}")
        return url
    except ClientError as e:
        if e.response['Error']['Code'] == 'QueueDoesNotExist':
             logger.error(f"SQS queue '{queue_name}' does not exist.")
        else:
             logger.exception(f"AWS ClientError getting SQS queue URL for '{queue_name}': {e}")
        return None
    except Exception as e:
         logger.exception(f"Unexpected error getting SQS queue URL for '{queue_name}'")
         return None

def send_sqs_message(queue_name, message_body_dict, message_group_id=None):
    """
    Sends a message (Python dict converted to JSON) to the specified SQS queue.
    Handles Decimal encoding and optional MessageGroupId for FIFO queues.
    Returns True on success, False on failure.
    """
    queue_url = get_queue_url(queue_name)
    if not queue_url:
        logger.error(f"Cannot send message, failed to get URL for queue: {queue_name}")
        return False # Error already logged by get_queue_url

    try:
        # Use DecimalEncoder for proper serialization if message contains Decimals
        message_body_str = json.dumps(message_body_dict, cls=DecimalEncoder)

        params = {
            'QueueUrl': queue_url,
            'MessageBody': message_body_str
        }
        # Add MessageGroupId if the queue URL indicates it's FIFO and ID is provided
        # Note: Standard queues ignore MessageGroupId
        if queue_url.endswith(".fifo") and message_group_id:
            params['MessageGroupId'] = str(message_group_id) # Must be string
            # Consider adding MessageDeduplicationId for FIFO if needed (e.g., content hash)
            # params['MessageDeduplicationId'] = hashlib.sha256(message_body_str.encode()).hexdigest()


        logger.debug(f"Sending SQS message to {queue_name} (URL: {queue_url})")
        # logger.debug(f"Message Body: {message_body_str}") # Be careful logging sensitive data
        if 'MessageGroupId' in params:
            logger.debug(f"Message Group ID: {params['MessageGroupId']}")

        sqs_client.send_message(**params)
        logger.info(f"Successfully sent message to SQS queue: {queue_name}")
        return True

    except ClientError as e:
        logger.exception(f"AWS ClientError sending message to SQS queue '{queue_name}': {e}")
        return False
    except TypeError as e:
         logger.exception(f"TypeError during JSON serialization for SQS message: {e}")
         return False
    except Exception as e:
         logger.exception(f"Unexpected error sending to SQS queue '{queue_name}'")
         return False


def extract_sqs_message_body(record):
    """
    Extracts and parses the JSON message body from a single SQS record.
    Handles cases where the body might be nested or not valid JSON.
    Returns the parsed Python dictionary or None if parsing fails.
    """
    if not record or not isinstance(record, dict):
        logger.warning("Invalid SQS record provided for extraction.")
        return None

    body_content = record.get("body")
    if not body_content:
        logger.warning("SQS record has no 'body'.")
        return None

    message_id = record.get('messageId', 'Unknown') # For logging context

    # Check if body is already a dict (e.g., direct Lambda test event simulation)
    # This is unlikely for real SQS events but useful for testing.
    if isinstance(body_content, dict):
        logger.debug(f"Record body for {message_id} is already a dict.")
        return body_content

    # If body is a string, try to parse it as JSON
    if isinstance(body_content, str):
        try:
            # Attempt to parse the body string directly as JSON
            parsed_body = json.loads(body_content)
            # Optional: Check if the actual message is nested further, e.g., SNS->SQS
            # if isinstance(parsed_body, dict) and 'Message' in parsed_body:
            #     nested_message_str = parsed_body['Message']
            #     if isinstance(nested_message_str, str):
            #         return json.loads(nested_message_str)
            #     else: # Handle case where 'Message' isn't a string
            #         logger.warning(f"Nested 'Message' field is not a string: {type(nested_message_str)}")
            #         return parsed_body # Return the outer dict?
            return parsed_body # Return the directly parsed body
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse SQS record body as JSON for message {message_id}: {e}")
            logger.debug(f"Record body snippet: {body_content[:100]}...")
            return None
        except Exception as e:
             logger.exception(f"Unexpected error processing SQS record body for message {message_id}")
             logger.debug(f"Record body snippet: {body_content[:100]}...")
             return None

    logger.warning(f"SQS record body is neither a dict nor a JSON string for message {message_id}: {type(body_content)}")
    return None

# Keep specific extractors if their logic differs significantly, otherwise use the generic one.
extract_game_from_sqs_record = extract_sqs_message_body
extract_reaction_from_sqs_record = extract_sqs_message_body