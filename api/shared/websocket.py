import os
import json
import boto3
from .response import response_payload, DecimalEncoder
from .db import websocket_table
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
