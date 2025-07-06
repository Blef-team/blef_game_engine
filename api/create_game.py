import uuid
import boto3
import time
import json
import random
import decimal
from shared.response import * 
from shared.db import save_in_dynamodb


def lambda_handler(event, context):
    try:
        game_uuid = str(uuid.uuid4())
        empty_game = {
            "game_uuid": game_uuid,
            "admin_nickname": None,
            "public": "false",
            "room": random.randrange(10, 100),
            "status": "Not started",
            "round_number": 0,
            "max_cards": 0,
            "players": [],
            "hands": [],
            "cp_nickname": None,
            "history": []
        }

        if save_in_dynamodb(empty_game):
            return response_payload(200, {"game_uuid": game_uuid})
        raise(Exception("Something went wrong - ended up with no response"))

    except Exception as err:
        return internal_error_payload(err)
