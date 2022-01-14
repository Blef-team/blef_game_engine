import boto3
import json
import time
from boto3.dynamodb.conditions import Attr, Key
import decimal

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table("games")

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return int(obj)
        return super(DecimalEncoder, self).default(obj)


def response_payload(status_code, body):
    return {
            'statusCode': status_code,
            'body': json.dumps(body, cls=DecimalEncoder),
            'headers': {
                'Access-Control-Allow-Headers':'Content-Type,X-Amz-Date,Authorization,X-Api-Key,x-api-key,X-Amz-Security-Token',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
                'Access-Control-Allow-Credentials': True,
                'Content-Type': 'application/json'
            },
        }


def error_payload(status_code, body):
    return response_payload(status_code, {"error": body})


def internal_error_payload(err, message=None):
    body = "Internal Lambda function error: {}".format(err)
    if message:
        body = "{}\n{}".format(body, message)
    return error_payload(500, body)


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
