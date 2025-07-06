import boto3
import json
import time
from boto3.dynamodb.conditions import Attr, Key
import decimal
from shared.response import * 
from shared.db import table



def query_dynamodb():
    now = decimal.Decimal(str(time.time()))
    diff = 1800
    response = table.query(
        IndexName="public-index",
        KeyConditionExpression=Key('public').eq("true"),
        FilterExpression=Attr('game_uuid').size().eq(36) & Attr('last_modified').gt(now - diff)
    )
    return response['Items']


def lambda_handler(event, context):
    try:
        games = query_dynamodb()
        games_info = [
            {
                "game_uuid": game["game_uuid"],
                "room": game["room"],
                "players": [p["nickname"] for p in game["players"]],
                "last_modified": game["last_modified"]
                } for game in games
            ]
        return response_payload(200, games_info)

    except Exception as err:
        return internal_error_payload(err)
