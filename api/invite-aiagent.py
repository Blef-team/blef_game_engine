import os
import time
import json
import uuid
import boto3
from boto3.dynamodb.conditions import Key
import decimal
from shared.response import * 
from shared.db import table, get_from_dynamodb
from shared.api_gateway import parse_event
from shared.inputs import is_valid_uuid


AGENT_MAPPING = json.loads(os.environ.get("agent_mapping"))


def update_in_dynamodb(game_uuid, players):
    table.update_item(
        Key={
            'game_uuid': game_uuid
        },
        UpdateExpression="set players = :players, last_modified = :last_modified",
        ExpressionAttributeValues={
            ':players': players,
            ':last_modified': decimal.Decimal(str(time.time()))
        },
        ReturnValues="NONE"
    )
    return True


def format_name(agent_name, num):
    enumerated_name = f"{agent_name}_{num+1}" if num else agent_name
    return f"{enumerated_name}_(AI)"


def set_nickname(agent_name, player_nicknames, i=0):
    """ Create an AI agent nickname """
    formatted_name = format_name(agent_name, i)
    if formatted_name in player_nicknames:
        return set_nickname(agent_name, player_nicknames, i+1)
    return formatted_name


def lambda_handler(event, context):
    try:
        body = parse_event(event)
        if not body:
            return request_error_payload(event)

        game_uuid = str(body.get("game_uuid"))
        if not is_valid_uuid(game_uuid):
            return parameter_error_payload("game_uuid", game_uuid, message="Invalid game UUID")

        game = get_from_dynamodb(game_uuid)
        if not game:
            return parameter_error_payload("game_uuid", game_uuid, message="Game does not exist")

        if game.get("status") != "Not started":
            return error_payload(403, "Game already started")

        admin_uuid = body.get("admin_uuid")

        if not admin_uuid:
            return parameter_error_payload("admin_uuid", admin_uuid, message="Admin UUID missing - please supply it")

        if not is_valid_uuid(admin_uuid):
            return parameter_error_payload("admin_uuid", admin_uuid, message="Invalid admin UUID")

        players = game.get("players")
        game_admin_uuid = [player["uuid"] for player in players if player["nickname"] == game.get("admin_nickname")][0]
        if game_admin_uuid != admin_uuid:
            return parameter_error_payload("admin_uuid", admin_uuid, message="Admin UUID does not match")

        if len(players) == 8:
            return error_payload(403, "Game room full")

        agent_name = body.get("agent_name")
        if not agent_name:
            return parameter_error_payload("agent_name", agent_name, message="Agent name missing - please supply it")

        agent_type = AGENT_MAPPING.get(agent_name)
        if not agent_type:
            return parameter_error_payload("agent_name", agent_type, message="Invalid agent_name")

        nickname = set_nickname(agent_name, [p["nickname"] for p in players])

        player_uuid = str(uuid.uuid4())
        player = {
            "uuid": player_uuid,
            "nickname": nickname,
            "n_cards": 0,
            "ai_agent": agent_type
            }
        players.append(player)

        update_in_dynamodb(game_uuid, players)

        payload = {"message": f"{nickname} joined the game"}
        return response_payload(200, payload)

    except Exception as err:
        return internal_error_payload(err)
