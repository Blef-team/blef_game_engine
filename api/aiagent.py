import boto3
import json
import agent
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


lambda_client = boto3.client('lambda')


def parse_event(event):
    # Basic input validation
    if not isinstance(event, dict):
        return False

    # Handle both direct triggers and API Gateway
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
    filtered_players = [p for p in players if p["nickname"] == nickname]
    if filtered_players:
        return filtered_players[0]


def get_aiagent_player_uuid(game):
    current_player = game["cp_nickname"]
    player_obj = get_player_by_nickname(game["players"], current_player)
    return player_obj.get("uuid")


def is_legal(action, history):
    if action not in range(89):
        return False
    if not history and action == 88 or history and action <= history[-1]["action_id"]:
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
    assert is_legal(action, game["history"])

    call_play(action, aiagent_player_uuid, game["game_uuid"])
    message = "Action made"
    return {
        'statusCode': 200,
        'body': json.dumps({"message": message})
    }
