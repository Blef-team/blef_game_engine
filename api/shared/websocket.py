import os
import json
import boto3
from boto3.dynamodb.conditions import Key
from concurrent.futures import ThreadPoolExecutor
from .response import response_payload, DecimalEncoder
from .db import websocket_table
from .game import censor_game, get_nickname_by_uuid
from .logging import logger

watch_game_websocket_api_id = os.environ.get("watch_game_websocket_api_id")
watch_game_websocket_api_stage = os.environ.get("watch_game_websocket_api_stage")

# Derived from the API id rather than looked up - fewer permissions, smaller control-plane throttling risk, slightly faster
endpoint_url = f"https://{watch_game_websocket_api_id}.execute-api.{os.environ['AWS_REGION']}.amazonaws.com/{watch_game_websocket_api_stage}"
apigateway = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)

# Upper bound on concurrent websocket posts per broadcast
MAX_BROADCAST_WORKERS = 16


def post_to_connection(payload, connection_id):
    """
    Sends a payload to a single websocket connection.
    Dropped connections are forgotten.
    """
    try:
        apigateway.post_to_connection(
            Data=bytes(json.dumps(response_payload(200, payload), cls=DecimalEncoder), encoding="utf-8"),
            ConnectionId=connection_id
        )
    except apigateway.exceptions.GoneException:
        websocket_table.delete_item(Key={'connection_id': connection_id})
    except Exception as err:
        # A single failure must not abort the rest of the broadcast.
        logger.info('## ERROR: COULD NOT POST TO CONNECTION')
        logger.info(str(err))
    return True


def find_connected_connections(game_uuid):
    """Connections watching a game. Round snapshots have the round suffix stripped to get the game UUID."""
    response = websocket_table.query(
        KeyConditionExpression=Key('game_uuid').eq(game_uuid.split("_")[0]),
        IndexName="game_uuid-index"
    )
    return [(c["connection_id"], c.get("player_uuid")) for c in response.get("Items", [])]


def broadcast_game_state(game, exclude_player_uuid=None):
    """
    Pushes a game state to everyone watching it, censored per recipient.
    `exclude_player_uuid` skips one player, in case the caller returns state to them in the HTTP response
    """
    recipients = [(connection_id, player_uuid)
                  for connection_id, player_uuid in find_connected_connections(game["game_uuid"])
                  if exclude_player_uuid is None or player_uuid != exclude_player_uuid]
    if not recipients:
        return

    def push(recipient):
        connection_id, player_uuid = recipient
        nickname = get_nickname_by_uuid(game.get("players", []), player_uuid)
        post_to_connection(censor_game(game, nickname), connection_id)

    with ThreadPoolExecutor(max_workers=min(len(recipients), MAX_BROADCAST_WORKERS)) as executor:
        list(executor.map(push, recipients))
