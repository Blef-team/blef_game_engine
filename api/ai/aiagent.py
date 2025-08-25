import boto3
import json
import agent
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

lambda_client = boto3.client('lambda')

def parse_event(event):
    if not isinstance(event, dict):
        return False
    body = event.get("body", event)
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError:
            return None
    path_params = event.get("pathParameters", {})
    query_params = event.get("queryStringParameters", {})
    body.update(path_params)
    body.update(query_params)
    return body

def get_player_by_nickname(players, nickname):
    return next((p for p in players if p["nickname"] == nickname), None)

def get_aiagent_player_uuid(game):
    current_player = game.get("cp_nickname")
    if not current_player:
        return None
    player_obj = get_player_by_nickname(game.get("players", []), current_player)
    return player_obj.get("uuid") if player_obj else None

def is_legal(action, game):
    """
    Checks if an action is legal based on the current game state and rules.
    """
    rules = game.get("rules", {})
    deck_size = rules.get("deck_size", 24)
    check_action_id = 140 if deck_size == 32 else 88
    
    if not (0 <= action <= check_action_id):
        return False
        
    history = game.get("history", [])
    
    if not history and action == check_action_id:
        return False
        
    if history and action < check_action_id:
        last_action_id = history[-1].get("action_id", -1)
        if action <= last_action_id:
            return False

    return True

def call_play(action, aiagent_player_uuid, game_uuid):
    """
        Invoke blef-play asynchronously
    """
    payload = {
        "action_id": action,
        "player_uuid": aiagent_player_uuid,
        "game_uuid": game_uuid
    }
    logger.info('## PAYLOAD')
    logger.info(payload)
    return lambda_client.invoke(
        FunctionName='blef-play',
        InvocationType='Event',
        Payload=json.dumps(payload)
    )

def lambda_handler(event, context):
    logger.info('## EVENT')
    logger.info(event)
    game = parse_event(event)
    logger.info('## GAME')
    logger.info(game)
    assert game

    aiagent_player_uuid = get_aiagent_player_uuid(game)
    assert aiagent_player_uuid

    action = agent.determine_action(game)
    logger.info('## ACTION')
    logger.info(action)
    assert is_legal(action, game)

    call_play(action, aiagent_player_uuid, game["game_uuid"])
    message = "Action made"
    return {
        'statusCode': 200,
        'body': json.dumps({"message": message})
    }
