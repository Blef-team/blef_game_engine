import uuid
import boto3
from boto3.dynamodb.conditions import Key
import time
import json
import decimal
from shared.response import * 
from shared.db import * 
from shared.api_gateway import parse_event
from shared.game import get_nickname_by_uuid, get_revealed_hands
from shared.inputs import is_valid_uuid




def update_in_dynamodb(game_uuid, public):
    table.update_item(
        Key={
            'game_uuid': game_uuid
        },
        UpdateExpression="set last_modified = :last_modified, #game_public = :public",
        ExpressionAttributeValues={
            ':last_modified': decimal.Decimal(str(time.time())),
            ':public': public
        },
        ExpressionAttributeNames={
            '#game_public': "public"
        },
        ReturnValues="NONE"
    )
    return True


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

        current_status = game.get("status")

        player_uuid = body.get("player_uuid")

        if player_uuid and not is_valid_uuid(player_uuid):
            return parameter_error_payload("player_uuid", player_uuid, message="Invalid player UUID")

        round = body.get("round")

        if round:
            if isinstance(round, str) and round.isdigit():
                round = int(round)
            elif isinstance(round, int):
                pass
            else:
                return parameter_error_payload("round", round)

        if round and round <= 0:
            return parameter_error_payload("round", round, message="The round parameter is invalid - must be an integer between 1 and the current round, or -1, or blank")
        current_round = game["round_number"]
        if round and current_round < round:
            return parameter_error_payload("round", round, message="The game has not reached this round")

        if round and (round != current_round or current_status != "Running"):
            game = get_from_dynamodb(f"{game_uuid}_{round}")
        else:
            round = current_round

        if player_uuid:
            player_nickname = get_nickname_by_uuid(game["players"], player_uuid)
            player_authenticated = bool(player_nickname)
            if not player_authenticated:
                return parameter_error_payload("player_uuid", player_uuid, message="The UUID does not match any active player")
        else:
            player_authenticated = False
            player_nickname = ''

        revealed_hands = get_revealed_hands(game, current_round, current_status, player_authenticated, player_nickname)

        private_players = []
        for player in game["players"]:
            private_players.append({key: player[key] for key in player if key != "uuid"})

        visible_game = {
            "admin_nickname": game["admin_nickname"],
            "public": game["public"],
            "room": game["room"],
            "status": game["status"],
            "round_number": game["round_number"],
            "max_cards": game["max_cards"],
            "players": private_players,
            "hands": revealed_hands,
            "cp_nickname": game["cp_nickname"],
            "history": game["history"],
            "last_modified": game["last_modified"]
        }

        return response_payload(200, visible_game)

    except Exception as err:
        return internal_error_payload(err)
