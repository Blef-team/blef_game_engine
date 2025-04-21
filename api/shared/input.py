import uuid
import json
import re
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- Constants ---
# Reaction validation pattern (example)
REACTION_PATTERN = r"^(😮|🤨|👏|😂|🦊)$"

def parse_api_gateway_event(event):
    """
    Parses API Gateway event (v1 payload format) to extract and combine
    body (if JSON), path parameters, and query string parameters into a single dict.
    Returns None if parsing fails or event format is unexpected.
    """
    if not isinstance(event, dict):
        logger.error("Input event is not a dictionary.")
        return None

    body = {}
    path_params = {}
    query_params = {}

    try:
        # Parse JSON body if present and valid
        body_content = event.get("body")
        if isinstance(body_content, str):
            try:
                body = json.loads(body_content)
                if not isinstance(body, dict): # Ensure parsed body is a dict
                     logger.warning(f"Event body parsed to non-dict type: {type(body)}")
                     body = {} # Treat as empty if not a dict
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse event body as JSON: {body_content[:100]}...") # Log snippet
                # Depending on requirements, might return error or continue with empty body
                # Returning None indicates a parsing failure that might warrant a bad request
                return None
        elif isinstance(body_content, dict):
             # Body might already be a dict (e.g., direct test invoke)
             body = body_content

        # Extract path and query parameters (ensure they are dicts)
        path_params = event.get("pathParameters") or {}
        query_params = event.get("queryStringParameters") or {}
        if not isinstance(path_params, dict): path_params = {}
        if not isinstance(query_params, dict): query_params = {}


        # Combine parameters: body takes precedence over path, path over query
        combined_params = {**query_params, **path_params, **body}
        logger.debug(f"Parsed event parameters: {combined_params}")
        return combined_params

    except Exception as e:
        logger.exception(f"Unexpected error parsing API Gateway event: {e}")
        logger.debug(f"Original event structure: {event}")
        return None # Indicate failure


def is_valid_uuid(value):
    """ Checks if a string value is a valid UUID. """
    if not isinstance(value, (str, uuid.UUID)):
        return False
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False

def is_valid_player_nickname(name):
    """ Checks if a nickname is valid (starts with letter, alphanumeric/underscore). """
    if not name or not isinstance(name, str):
        return False
    # Regex: Starts with a letter, followed by zero or more word characters (letters, numbers, underscore)
    return bool(re.match(r"^[a-zA-Z]\w*$", name))

def is_valid_agent_name(name):
    """ Checks if an agent name (used in config/env vars) is valid. """
    # Allows alphanumeric, hyphen, underscore. Adjust pattern as needed.
    if not name or not isinstance(name, str):
        return False
    pattern = re.compile(r"^[a-zA-Z0-9-_]+$")
    return bool(pattern.match(name))

def is_valid_reaction(reaction_string):
    """ Checks if the reaction string matches the allowed emoji pattern. """
    if not reaction_string or not isinstance(reaction_string, str):
        return False
    return bool(re.fullmatch(REACTION_PATTERN, reaction_string))

def get_connection_id(event):
    """
    Extracts WebSocket connection ID from various possible event locations
    (primarily requestContext for API Gateway events).
    Raises ValueError if connection ID cannot be found.
    """
    # Check requestContext first (standard for API GW WebSocket events)
    request_context = event.get("requestContext", {})
    connection_id = request_context.get("connectionId")

    # Fallback for potential direct invokes or other structures
    if not connection_id:
         connection_id = event.get("connectionId") # Top-level key

    if not connection_id:
        logger.error(f"Could not extract connectionId from event: {event}")
        raise ValueError("Connection ID not found in event") # Raise specific error

    logger.debug(f"Extracted connection ID: {connection_id}")
    return connection_id
