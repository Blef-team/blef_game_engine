import boto3
import json
import logging
import re # For function name validation
from botocore.exceptions import ClientError # Import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

lambda_client = boto3.client('lambda')

def lambda_function_exists(function_name):
    """ Checks if a Lambda function with the given name exists. """
    if not function_name or not isinstance(function_name, str):
        logger.error("Invalid function_name provided for existence check.")
        return False
    try:
        lambda_client.get_function(FunctionName=function_name)
        logger.debug(f"Lambda function '{function_name}' found.")
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            logger.warning(f"Lambda function '{function_name}' not found.")
            return False
        else:
            # Log other AWS errors but assume doesn't exist on error
            logger.exception(f"AWS ClientError checking existence of Lambda {function_name}: {e}")
            return False
    except Exception as e:
        logger.exception(f"Unexpected error checking existence of Lambda {function_name}: {e}")
        return False # Safer to assume not found on unexpected error

def invoke_lambda_async(function_name, payload_dict):
    """ Invokes another Lambda function asynchronously (Event invocation). """
    if not function_name or not isinstance(function_name, str):
        logger.error("Invalid function_name provided for async invocation.")
        return False
    if not isinstance(payload_dict, dict):
        logger.error("Invalid payload_dict (must be a dictionary) provided for async invocation.")
        return False

    try:
        # Convert payload dict to JSON string
        payload_json = json.dumps(payload_dict)

        logger.info(f"Invoking Lambda '{function_name}' asynchronously.")
        # logger.debug(f"Payload: {payload_json}") # Be careful logging sensitive data

        lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='Event', # Asynchronous invocation
            Payload=payload_json
        )
        logger.info(f"Successfully submitted async invocation for '{function_name}'.")
        return True
    except ClientError as e:
         logger.exception(f"AWS ClientError invoking {function_name} asynchronously: {e}")
         return False
    except TypeError as e:
         logger.exception(f"TypeError during JSON serialization for invoking {function_name}: {e}")
         return False
    except Exception as e:
        logger.exception(f"Failed to invoke {function_name} asynchronously: {e}")
        return False

def call_play_lambda(action_id, player_uuid, game_uuid):
    """ Constructs payload and invokes the 'blef-play' Lambda asynchronously. """
    # Consider making the target function name an environment variable
    target_function_name = 'blef-play' # Or os.environ.get("PLAY_FUNCTION_NAME", "blef-play")

    payload = {
        "action_id": action_id,
        "player_uuid": player_uuid,
        "game_uuid": game_uuid
    }
    logger.info(f"Invoking {target_function_name} with payload: {payload}")
    return invoke_lambda_async(target_function_name, payload)

def call_ai_agent_lambda(agent_type, game_state_dict):
    """
    Constructs function name and invokes the specific AI agent Lambda asynchronously.
    Validates agent_type format and checks if the target function exists.
    """
    if not agent_type or not isinstance(agent_type, str):
        logger.error("Invalid agent_type provided.")
        return False
    if not isinstance(game_state_dict, dict):
         logger.error("Invalid game_state_dict provided.")
         return False

    # Basic validation for agent_type characters to prevent unexpected function names
    if not re.match(r"^[a-zA-Z0-9-_]+$", agent_type):
         logger.error(f"Invalid characters in agent_type: '{agent_type}'")
         return False

    # Construct target function name (consider making prefix configurable)
    # function_name_prefix = os.environ.get("AI_AGENT_PREFIX", "blef-aiagent-")
    function_name = f'blef-aiagent-{agent_type}' # Using hardcoded prefix as before
    logger.info(f"Attempting to invoke AI agent: {function_name}")

    # Check if the target Lambda function actually exists before invoking (optional but recommended)
    if not lambda_function_exists(function_name):
        logger.error(f"Target AI agent Lambda function '{function_name}' does not exist or check failed.")
        return False

    logger.info(f"Invoking {function_name} with game state for game {game_state_dict.get('game_uuid')}")
    return invoke_lambda_async(function_name, game_state_dict)