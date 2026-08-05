from boto3.dynamodb.conditions import Key
from concurrent.futures import ThreadPoolExecutor
import json
from shared.api_gateway import parse_event
from shared.logging import logger
from shared.db import websocket_table, get_from_dynamodb
from shared.websocket import post_to_connection, MAX_BROADCAST_WORKERS


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

    target_connection_ids = []
    for connection in connections:
        if target_team:
            player_uuid = connection.get("player_uuid")
            if not player_uuid:
                continue # Observers don't get team-only reactions

            player = next((p for p in game_players if p["uuid"] == player_uuid), None)
            if not player or player.get("team") != target_team:
                continue # Skip players not on the target team

        target_connection_ids.append(connection["connection_id"])

    if not target_connection_ids:
        return

    with ThreadPoolExecutor(max_workers=min(len(target_connection_ids), MAX_BROADCAST_WORKERS)) as executor:
        list(executor.map(lambda connection_id: post_to_connection(reaction_details, connection_id), target_connection_ids))

def lambda_handler(event, context): 
    logger.info('## EVENT') 
    logger.info(event) 
    for record in parse_event(event)['Records']:
        message_details = json.loads(record.get("body"))
        broadcast_reaction(message_details)
    return True
