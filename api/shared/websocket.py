import boto3
import json
import os
import logging
import time
import decimal
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

# Import shared modules using the new style
from shared import db as db # Use alias to avoid conflict
from shared import game # Use direct name

# Assuming logger is configured elsewhere
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- Configuration ---
WEBSOCKET_TABLE_NAME = os.environ.get("WEBSOCKET_TABLE_NAME", "watch_game_websocket_manager")
WEBSOCKET_API_ID = os.environ.get("WATCH_GAME_WEBSOCKET_API_ID")
WEBSOCKET_API_STAGE = os.environ.get("WATCH_GAME_WEBSOCKET_API_STAGE")

# --- Error Handling for Configuration ---
_config_error = None
if not WEBSOCKET_API_ID: _config_error = "WATCH_GAME_WEBSOCKET_API_ID not set."
if not WEBSOCKET_API_STAGE: _config_error = "WATCH_GAME_WEBSOCKET_API_STAGE not set."
if not WEBSOCKET_TABLE_NAME: _config_error = "WEBSOCKET_TABLE_NAME not set or default invalid."

if _config_error:
    logger.critical(f"WebSocket Configuration Error: {_config_error}")
    # Option 1: Raise error immediately to prevent lambda cold start success
    raise EnvironmentError(f"WebSocket Configuration Error: {_config_error}")
    # Option 2: Allow lambda to load but fail on first use (handled below)

# --- Boto3 Clients Initialization ---
dynamodb_resource = None
websocket_table = None
apigateway_management_client = None
_initialization_error = None

try:
    if not _config_error: # Only proceed if config seems okay
        # DynamoDB Table Resource for WebSocket Connections
        dynamodb_resource = boto3.resource('dynamodb')
        websocket_table = dynamodb_resource.Table(WEBSOCKET_TABLE_NAME)

        # API Gateway Management API Client
        apigw_v2_client = boto3.client('apigatewayv2')
        api_endpoint_data = apigw_v2_client.get_api(ApiId=WEBSOCKET_API_ID)
        api_endpoint = api_endpoint_data.get('ApiEndpoint')

        if not api_endpoint:
             raise ValueError(f"Could not retrieve API Endpoint for API ID {WEBSOCKET_API_ID}")

        endpoint_url = f"https://{api_endpoint}/{WEBSOCKET_API_STAGE}".replace("wss://", "https://")
        logger.info(f"Initializing APIGatewayManagementAPI client for endpoint: {endpoint_url}")
        apigateway_management_client = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)

except ClientError as e:
     _initialization_error = f"AWS ClientError during WebSocket utils initialization: {e}"
     logger.critical(_initialization_error)
except Exception as e:
     _initialization_error = f"Unexpected error during WebSocket utils initialization: {e}"
     logger.critical(_initialization_error)


# --- Helper to Check Initialization ---
def _check_init():
    if _config_error: raise EnvironmentError(_config_error)
    if _initialization_error: raise RuntimeError(f"WebSocket client initialization failed: {_initialization_error}")
    if not websocket_table or not apigateway_management_client:
         raise RuntimeError("WebSocket clients (DynamoDB Table or API Gateway Management) are not initialized.")


# --- DynamoDB Operations for Connections ---

def save_connection(connection_id, game_uuid=None, player_uuid=None, reactions_enabled=False):
    """ Saves WebSocket connection details to the manager table. """
    _check_init() # Check if clients are ready
    try:
        item = {
            'connection_id': connection_id,
            'last_modified': decimal.Decimal(str(time.time())),
            'reactions_enabled': "true" if reactions_enabled else "false"
        }
        # Add optional fields only if they have values
        if game_uuid: item['game_uuid'] = game_uuid
        if player_uuid: item['player_uuid'] = player_uuid

        websocket_table.put_item(Item=item)
        logger.info(f"Saved WebSocket connection: {connection_id} (Game: {game_uuid}, Player: {player_uuid})")
        return True
    except ClientError as e:
        logger.exception(f"DynamoDB Error saving connection {connection_id}: {e}")
        return False
    except Exception as e:
         logger.exception(f"Unexpected error saving connection {connection_id}")
         return False

def delete_connection(connection_id):
    """ Deletes WebSocket connection details from the manager table. """
    _check_init()
    if not connection_id: return False # Cannot delete without ID
    try:
        websocket_table.delete_item(Key={'connection_id': connection_id})
        logger.info(f"Deleted WebSocket connection: {connection_id}")
        return True
    except ClientError as e:
        # Log error but don't fail disconnect handler catastrophically
        logger.error(f"DynamoDB Error deleting connection {connection_id}: {e}")
        return False # Indicate failure
    except Exception as e:
         logger.exception(f"Unexpected error deleting connection {connection_id}")
         return False


def _query_or_scan_connections(index_name=None, key_condition=None, filter_expression=None):
    """ Internal helper for querying or scanning the connections table with pagination. """
    _check_init()
    items = []
    params = {}
    last_evaluated_key = None

    if index_name: params['IndexName'] = index_name
    if key_condition: params['KeyConditionExpression'] = key_condition
    if filter_expression: params['FilterExpression'] = filter_expression

    operation = websocket_table.query if key_condition else websocket_table.scan

    try:
        while True:
            if last_evaluated_key:
                params['ExclusiveStartKey'] = last_evaluated_key

            response = operation(**params)
            items.extend(response.get("Items", []))
            last_evaluated_key = response.get('LastEvaluatedKey', None)

            if not last_evaluated_key:
                break # Exit loop if no more pages
            logger.info(f"Paginating connection {'query' if key_condition else 'scan'}...")

    except ClientError as e:
        logger.exception(f"DynamoDB Error finding connections: {e}")
        return [] # Return empty on error
    except Exception as e:
        logger.exception(f"Unexpected error finding connections")
        return []

    logger.info(f"Found {len(items)} connections matching criteria.")
    return items


def find_connections_by_game(game_uuid, reactions_only=False):
    """ Finds connection details associated with a specific game UUID using GSI. """
    if not game_uuid: return []
    base_game_uuid = str(game_uuid).split("_")[0] # Use base UUID for lookup
    logger.debug(f"Querying connections GSI 'game_uuid-index' for game: {base_game_uuid}")

    key_cond = Key('game_uuid').eq(base_game_uuid)
    filter_expr = Attr('reactions_enabled').eq("true") if reactions_only else None

    connections = _query_or_scan_connections(
        index_name="game_uuid-index", # Assumes GSI named 'game_uuid-index'
        key_condition=key_cond,
        filter_expression=filter_expr
    )
    # Returns list of full connection item dicts
    return connections


def find_public_watchers():
    """ Finds connection details for watchers of the public games list (scan, use cautiously). """
    logger.debug("Scanning connections table for public watchers (no game_uuid).")
    # Filter where the game_uuid attribute does not exist
    filter_expr = Attr('game_uuid').not_exists()
    connections = _query_or_scan_connections(filter_expression=filter_expr)
    # Returns list of full connection item dicts
    return connections


# --- API Gateway Management API Operations ---

def post_to_connection(connection_id, payload_dict):
    """ Sends a JSON payload (dict) to a specific WebSocket connection ID. """
    _check_init()
    if not connection_id:
        logger.warning("post_to_connection called with empty connection_id.")
        return False

    try:
        # Use the DecimalEncoder from db module for consistency
        data_bytes = bytes(json.dumps(payload_dict, cls=db.DecimalEncoder), encoding='utf-8')

        # Limit logging of potentially large/sensitive payloads
        logger.debug(f"Posting to connection {connection_id}. Payload size: {len(data_bytes)} bytes.")
        # if len(data_bytes) < 500: logger.debug(f"Payload: {data_bytes.decode()}") # Log small payloads

        apigateway_management_client.post_to_connection(
            Data=data_bytes,
            ConnectionId=connection_id
        )
        logger.debug(f"Successfully posted to connection {connection_id}.")
        return True

    except apigateway_management_client.exceptions.GoneException:
        logger.warning(f"Connection {connection_id} is gone (GoneException). Cleaning up DB entry.")
        # Attempt to clean up the stale connection from DynamoDB
        delete_connection(connection_id) # Fire and forget cleanup
        return False # Indicate message wasn't delivered
    except ClientError as e:
        # Handle other potential errors (e.g., throttling, permissions)
        logger.error(f"AWS ClientError posting to connection {connection_id}: {e}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error posting to connection {connection_id}")
        return False


def broadcast_message(connection_id_list, payload_dict):
    """ Sends a payload dict to multiple connection IDs. """
    if not connection_id_list:
        logger.info("Broadcast requested but connection ID list is empty.")
        return 0, 0 # Success, Failures

    success_count = 0
    failure_count = 0
    total = len(connection_id_list)
    logger.info(f"Broadcasting message to {total} connection IDs.")

    for connection_id in connection_id_list:
         if post_to_connection(connection_id, payload_dict):
             success_count += 1
         else:
             failure_count += 1 # Includes GoneException cleanups

    logger.info(f"Broadcast finished. Success: {success_count}/{total}, Failures/Gone: {failure_count}/{total}")
    return success_count, failure_count


# --- Combined Operations ---

def broadcast_game_state(game_state_dict):
     """ Finds relevant game watchers and broadcasts the censored game state to each. """
     game_uuid = game_state_dict.get("game_uuid")
     if not game_uuid:
          logger.error("Cannot broadcast game state without game_uuid.")
          return

     connections = find_connections_by_game(game_uuid)
     if not connections:
         logger.info(f"No connections found watching game {game_uuid}, skipping broadcast.")
         return

     logger.info(f"Broadcasting game state for {game_uuid} to {len(connections)} watchers.")
     success = 0
     failures = 0
     for conn in connections:
         connection_id = conn.get("connection_id")
         player_uuid = conn.get("player_uuid") # Could be None

         if not connection_id: continue # Skip if connection_id is missing

         # Censor state based on the watcher's player_uuid
         visible_game = game.censor_game_state(game_state_dict, player_uuid)
         if not visible_game:
              logger.error(f"Failed to censor game state for watcher {connection_id} on game {game_uuid}")
              failures += 1
              continue # Skip posting if censoring failed

         if post_to_connection(connection_id, visible_game):
              success += 1
         else:
              failures +=1
     logger.info(f"Game state broadcast complete for {game_uuid}. Success: {success}, Failures/Gone: {failures}")


def broadcast_public_game_update(game_state_dict):
    """ Finds public watchers and broadcasts summarized public game info. """
    watchers = find_public_watchers() # Returns list of connection dicts
    if not watchers:
        logger.info("No public game watchers found, skipping public broadcast.")
        return

    # Extract necessary info for public view
    game_uuid = game_state_dict.get("game_uuid")
    is_public = game_state_dict.get("public") == "true"

    # Construct payload: only include details if game is public
    # Send minimal payload even if becoming private (to signal removal)
    public_info = {
        "type": "public_game_update", # Add type for client handling
        "game_uuid": game_uuid,
        "public": "true" if is_public else "false", # Send current status
        "last_modified": game_state_dict.get("last_modified"),
        # Only include other details if currently public
        **({
            "room": game_state_dict.get("room"),
            "players": [p.get("nickname") for p in game_state_dict.get("players", []) if p.get("nickname")],
            "status": game_state_dict.get("status"),
           } if is_public else {})
    }

    connection_ids = [w.get("connection_id") for w in watchers if w.get("connection_id")]
    broadcast_message(connection_ids, public_info)


def broadcast_reaction(reaction_details_dict):
     """ Broadcasts a reaction message to watchers of that game with reactions enabled. """
     game_uuid = reaction_details_dict.get("game_uuid")
     if not game_uuid:
          logger.error("Cannot broadcast reaction without game_uuid.")
          return

     # Find connections for this game that have reactions_enabled='true'
     connections = find_connections_by_game(game_uuid, reactions_only=True)
     if not connections:
         logger.info(f"No reaction-enabled watchers found for game {game_uuid}.")
         return

     connection_ids = [c.get("connection_id") for c in connections if c.get("connection_id")]
     logger.info(f"Broadcasting reaction to {len(connection_ids)} watchers for game {game_uuid}.")

     # Add type to payload for client-side routing
     payload = {**reaction_details_dict, "type": "reaction"}
     broadcast_message(connection_ids, payload)