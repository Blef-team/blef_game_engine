import os
import boto3
from boto3.dynamodb.conditions import Key
import json
import decimal
from shared.response import * 
from shared.api_gateway import parse_event
from shared.logging import logger


watch_game_websocket_api_id = os.environ.get("watch_game_websocket_api_id")
watch_game_websocket_api_stage = os.environ.get("watch_game_websocket_api_stage")

endpoint_url = f"{boto3.client('apigatewayv2').get_api(ApiId=watch_game_websocket_api_id).get('ApiEndpoint')}/{watch_game_websocket_api_stage}".replace("wss://", "https://")
apigateway = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)

dynamodb = boto3.resource('dynamodb')
websocket_table = dynamodb.Table("watch_game_websocket_manager")


def find_connected_players(game_uuid):
    watched_game_uuid = game_uuid.split("_")[0]
    response = websocket_table.query(
        KeyConditionExpression=Key('game_uuid').eq(watched_game_uuid),
        IndexName="game_uuid-index"
    )
    return [connection["connection_id"] for connection in response.get("Items", []) if connection.get("reactions_enabled") == "true"]


def post_to_connection(payload, connection_id):
    logger.info('## POSTING TO CONNECTION')
    logger.info(connection_id)
    response = apigateway.post_to_connection(
        Data=bytes(json.dumps(response_payload(200, payload), cls=DecimalEncoder), encoding="utf-8"),
        ConnectionId=connection_id
    )
    return True


def broadcast_reaction(reaction_details):
    connected_players = find_connected_players(reaction_details.get("game_uuid"))
    for connection_id in connected_players:
        post_to_connection(reaction_details, connection_id)


def lambda_handler(event, context): 
    logger.info('## EVENT') 
    logger.info(event) 
    for record in parse_event(event)['Records']:
        message_details = json.loads(record.get("body"))
        broadcast_reaction(message_details)
    return True
