import os
import boto3
from boto3.dynamodb.conditions import Key
import json
from shared.response import * 
from shared.api_gateway import parse_event
from shared.logging import logger
from shared.db import websocket_table, get_from_dynamodb


watch_game_websocket_api_id = os.environ.get("watch_game_websocket_api_id")
watch_game_websocket_api_stage = os.environ.get("watch_game_websocket_api_stage")

endpoint_url = f"{boto3.client('apigatewayv2').get_api(ApiId=watch_game_websocket_api_id).get('ApiEndpoint')}/{watch_game_websocket_api_stage}".replace("wss://", "https://")
apigateway = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)

def post_to_connection(payload, connection_id):
    logger.info('## POSTING TO CONNECTION')
    logger.info(connection_id)
    response = apigateway.post_to_connection(
        Data=bytes(json.dumps(response_payload(200, payload), cls=DecimalEncoder), encoding="utf-8"),
        ConnectionId=connection_id
    )
    return True


def broadcast_reaction(reaction_details):
    watched_game_uuid = reaction_details.get("game_uuid").split("_")[0]
    target_team = reaction_details.get("target_team")
    
    # If it's a team-only reaction, fetch the game to map player UUIDs to teams
    game_players = []
    if target_team:
        game = get_from_dynamodb(watched_game_uuid)
        if game:
            game_players = game.get("players", [])

    response = websocket_table.query(
        KeyConditionExpression=Key('game_uuid').eq(watched_game_uuid),
        IndexName="game_uuid-index"
    )
    connections = [conn for conn in response.get("Items", []) if conn.get("reactions_enabled") == "true"]
    
    for connection in connections:
        if target_team:
            player_uuid = connection.get("player_uuid")
            if not player_uuid:
                continue # Observers don't get team-only reactions
                
            player = next((p for p in game_players if p["uuid"] == player_uuid), None)
            if not player or player.get("team") != target_team:
                continue # Skip players not on the target team
                
        post_to_connection(reaction_details, connection["connection_id"]) 

def lambda_handler(event, context): 
    logger.info('## EVENT') 
    logger.info(event) 
    for record in parse_event(event)['Records']:
        message_details = json.loads(record.get("body"))
        broadcast_reaction(message_details)
    return True
