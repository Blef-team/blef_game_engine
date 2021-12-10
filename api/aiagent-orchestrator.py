import boto3
import json
import re


lambda_client = boto3.client('lambda')


def get_player_by_nickname(players, nickname):
    filtered_players = [p for p in players if p["nickname"] == nickname]
    if filtered_players:
        return filtered_players[0]


def get_aiagent_name(game):
    current_player = game["cp_nickname"]
    player_obj = get_player_by_nickname(game["players"], current_player)
    return player_obj.get("ai_agent")


def name_valid(name):
    pattern = re.compile(r"^[a-zA-Z0-9-_]+$")
    return name and isinstance(name, str) and pattern.match(name)


def lambda_function_exists(name):
    try:
        response = lambda_client.get_function(FunctionName=name)
    except lambda_client.exceptions.ResourceNotFoundException:
        return False
    return response.get("ResponseMetadata").get("HTTPStatusCode") == 200


def call_aiagent(payload):
    """
        Invoke blef-aiagent-[...] asynchronously
    """
    agent_name = get_aiagent_name(payload)
    function_name = f'blef-aiagent-{agent_name}'
    if name_valid(agent_name) and lambda_function_exists(function_name):
        return lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='Event',
            Payload=json.dumps(payload)
            )


def get_game(record):
    if not record.get("body"):
        return
    if not isinstance(record.get("body"), dict):
        try:
            return json.loads(record.get("body"))
        except ValueError as e:
            return


def lambda_handler(event, context):
    for record in event['Records']:
        game = get_game(record)
        if not game:
            continue
        call_aiagent(game)
    message = "Messages processed"
    return {
        'statusCode': 200,
        'body': json.dumps({"message": message})
    }
