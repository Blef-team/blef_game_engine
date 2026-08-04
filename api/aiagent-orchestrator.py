import boto3
import json
import re
from shared.game import get_player_by_nickname
from shared.logging import logger


lambda_client = boto3.client('lambda')


def get_aiagent_name(game):
    current_player = game["cp_nickname"]
    player_obj = get_player_by_nickname(game["players"], current_player)
    return player_obj.get("ai_agent")


def name_valid(name):
    pattern = re.compile(r"^[a-zA-Z0-9-_]+$")
    return name and isinstance(name, str) and pattern.match(name)


def call_aiagent(payload):
    """
        Invoke blef-aiagent-[...] asynchronously
    """
    agent_name = get_aiagent_name(payload)
    logger.info("## AGENT_NAME")
    logger.info(agent_name)
    if not name_valid(agent_name):
        logger.error(f"## REFUSING TO INVOKE AN AGENT WITH AN UNUSABLE NAME: {agent_name}")
        return
    function_name = f'blef-aiagent-{agent_name}'
    try:
        return lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='Event',
            Payload=json.dumps(payload)
            )
    except lambda_client.exceptions.ResourceNotFoundException:
        logger.error(f"## NO SUCH AI AGENT FUNCTION: {function_name}")


def get_game(record):
    if not record.get("body"):
        return
    if not isinstance(record.get("body"), dict):
        try:
            return json.loads(record.get("body"))
        except ValueError as e:
            return


def lambda_handler(event, context):
    logger.info('## EVENT')
    logger.info(event)

    for record in event['Records']:
        game = get_game(record)
        logger.info("## GAME")
        logger.info(game)
        if not game:
            continue
        call_aiagent(game)
    message = "Messages processed"
    return {
        'statusCode': 200,
        'body': json.dumps({"message": message})
    }
