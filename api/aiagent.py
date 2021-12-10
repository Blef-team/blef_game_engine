import boto3
import json
import os
import agent


AIAGENT_NAME = os.environ.get('AWS_LAMBDA_FUNCTION_NAME').replace("blef-aiagent-", "")
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
    if player_obj.get("ai_agent") != AIAGENT_NAME:
        return
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
    return lambda_client.invoke(
        FunctionName=f'blef-play',
        InvocationType='Event',
        Payload=json.dumps(payload)
        )


def lambda_handler(event, context):
    game = parse_event(event)
    assert game

    aiagent_player_uuid = get_aiagent_player_uuid(game)
    assert aiagent_player_uuid

    action = agent.determine_action(game)
    assert is_legal(action, game["history"])

    call_play(action, aiagent_player_uuid, game["game_uuid"])

    message = "Action made"
    return {
        'statusCode': 200,
        'body': json.dumps({"message": message})
    }
