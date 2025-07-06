import uuid
import boto3
from boto3.dynamodb.conditions import Key
import time
import json
from itertools import islice, product
import decimal
from shared.response import * 
from shared.db import *
from shared.api_gateway import parse_event


def is_valid_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


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

        if game.get("status") != "Not started":
            return error_payload(403, "Cannot make the change - game already started")

        admin_uuid = str(body.get("admin_uuid"))

        if not admin_uuid:
            return parameter_error_payload("admin_uuid", admin_uuid, message="Admin UUID missing - please supply it")

        if not is_valid_uuid(admin_uuid):
            return parameter_error_payload("admin_uuid", admin_uuid, message="Invalid admin UUID")

        players = game.get("players")
        game_admin_uuid = [player["uuid"] for player in players if player["nickname"] == game.get("admin_nickname")][0]
        if game_admin_uuid != admin_uuid:
            return parameter_error_payload("admin_uuid", admin_uuid, message="Admin UUID does not match")

        if game.get("public") == "true":
            return response_payload(200, {"message": "Request redundant - game already public"})

        public = "true"

        update_in_dynamodb(game_uuid, public)

        return response_payload(200, {"message": "Game made public"})

    except Exception as err:
        return internal_error_payload(err)
