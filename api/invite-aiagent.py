import os
import time
import json
import uuid
import decimal
from shared.response import response_payload, parameter_error_payload, error_payload, internal_error_payload
from shared.db import table
from shared.constants import GameStatus
from shared.game import calculate_actual_max_cards, unset_human_readiness
from shared.inputs import parse_team
from shared.decorators import validate_game_request

AGENT_MAPPING = json.loads(os.environ.get("agent_mapping"))

def update_in_dynamodb(game_uuid, players, max_cards):
    table.update_item(
        Key={
            'game_uuid': game_uuid
        },
        UpdateExpression="set players = :players, last_modified = :last_modified, max_cards = :mc",
        ExpressionAttributeValues={
            ':players': players,
            ':last_modified': decimal.Decimal(str(time.time())),
            ':mc': max_cards
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


@validate_game_request(
    require_admin=True, 
    required_status=GameStatus.NOT_STARTED, 
    status_error_message="Game already started"
)
def lambda_handler(event, context, body, game):
    try:
        players = game.get("players", [])
        if len(players) == 8:
            return error_payload(403, "Game room full")

        agent_name = body.get("agent_name")
        if not agent_name:
            return parameter_error_payload("agent_name", agent_name, message="Agent name missing - please supply it")

        agent_type = AGENT_MAPPING.get(agent_name)
        if not agent_type:
            return parameter_error_payload("agent_name", agent_name, message="Invalid agent_name")

        try:
            team = parse_team(body.get("team"))
        except ValueError as err:
            return parameter_error_payload("team", body.get("team"), message=str(err))

        nickname = set_nickname(agent_name, [p["nickname"] for p in players])

        player = {
            "uuid": str(uuid.uuid4()),
            "nickname": nickname,
            "n_cards": 0,
            "ai_agent": agent_type,
            "ready": True,
            "team": team
        }
        players.append(player)
        if team is not None:
            players = unset_human_readiness(players)

        max_cards = calculate_actual_max_cards(game.get("rules", {}), len(players))
        update_in_dynamodb(game["game_uuid"], players, max_cards)

        return response_payload(200, {"message": f"{nickname} joined the game"})

    except Exception as err:
        return internal_error_payload(err)
