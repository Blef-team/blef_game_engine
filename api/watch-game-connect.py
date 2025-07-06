import uuid
import boto3
from boto3.dynamodb.conditions import Key
import time
import json
import decimal
import logging
from shared.response import * 
from shared.api_gateway import parse_event
from shared.game import get_nickname_by_uuid
logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
games_table = dynamodb.Table("games")
websocket_table = dynamodb.Table("watch_game_websocket_manager")


def is_valid_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def get_game(game_uuid):
    response = games_table.query(KeyConditionExpression=Key('game_uuid').eq(game_uuid))
    items = response.get("Items")
    if len(items) == 1:
        return items[0]
    return None


def save_connection_object(obj):
    obj["last_modified"] = decimal.Decimal(str(time.time()))
    websocket_table.put_item(Item=obj)
    return True


def get_connection_id(event, context, body):
    if context and hasattr(context, 'get') and context.get("connectionId"):
        return context.get("connectionId")
    if "connectionId" in event.get("requestContext", {}):
        return event["requestContext"]["connectionId"]
    if "connectionId" in event:
        return event["connectionId"]
    if "connectionId" in body:
        return body["connectionId"]
    raise ValueError("Request context is invalid!")



def register_game_watcher(game_uuid, player_uuid, reactions_enabled, connection_id):
    if game_uuid and not is_valid_uuid(game_uuid):
        return parameter_error_payload("game_uuid", game_uuid, message="Invalid game UUID")

    game = get_game(game_uuid)
    if not game:
        return parameter_error_payload("game_uuid", game_uuid, message="Game does not exist")

    if player_uuid:
        if not is_valid_uuid(player_uuid):
            return parameter_error_payload("player_uuid", player_uuid, message="Invalid player UUID")
        player_nickname = get_nickname_by_uuid(game["players"], player_uuid)
        player_authenticated = bool(player_nickname)
        if not player_authenticated:
            return parameter_error_payload("player_uuid", player_uuid, message="The UUID does not match any active player")

    connection_object = {
        "connection_id": connection_id,
        "game_uuid": game_uuid,
        "player_uuid": player_uuid,
        "reactions_enabled": reactions_enabled
    }

    if save_connection_object(connection_object):
        return response_payload(200, {"message": "Connected"})


def register_public_games_watcher(reactions_enabled, connection_id):
    connection_object = {
        "connection_id": connection_id,
        "reactions_enabled": reactions_enabled
    }

    if save_connection_object(connection_object):
        return response_payload(200, {"message": "Connected"})


def register_watcher(game_uuid, player_uuid, reactions_enabled, connection_id):
    if reactions_enabled != "true":
        reactions_enabled = "false"    
    
    if not game_uuid and not player_uuid:
        payload = register_public_games_watcher(reactions_enabled, connection_id)
    else:
        payload = register_game_watcher(game_uuid, player_uuid, reactions_enabled, connection_id)

    if payload:
        return payload


def lambda_handler(event, context):
    try:
        body = parse_event(event)

        connection_id = get_connection_id(event, context, body)

        game_uuid = event.get("headers", {}).get("game_uuid") if "game_uuid" not in body else body["game_uuid"]
        logger.info('## GAME UUID:')
        logger.info(game_uuid)
        player_uuid = event.get("headers", {}).get("player_uuid") if "player_uuid" not in body else body["player_uuid"]
        logger.info('## PLAYER UUID:')
        logger.info(player_uuid)
        reactions_enabled = event.get("headers", {}).get("reactions_enabled") if "reactions_enabled" not in body else body["reactions_enabled"]
        logger.info('## REACTIONS ENABLED:')
        logger.info(reactions_enabled)

        payload = register_watcher(game_uuid, player_uuid, reactions_enabled, connection_id)

        if payload:
            return payload

        raise(Exception("Something went wrong - ended up with no response"))

    except Exception as err:
        return internal_error_payload(err)
