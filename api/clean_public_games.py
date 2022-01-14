import boto3
import json
import time
from boto3.dynamodb.conditions import Attr, Key

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table("games")

def response_payload(status_code, body):
    return {
            'statusCode': status_code,
            'body': json.dumps(body),
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


def get_public_games():
    response = table.query(
        IndexName="public-index",
        KeyConditionExpression=Key('public').eq("true"),
        ProjectionExpression="game_uuid,last_modified"
    )
    return response['Items']


def set_game_private(game_uuid, public):
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


def is_too_old(game, now, diff = 600):
    return (now - game["last_modified"]) > diff


def lambda_handler(event, context):
    try:
        now = decimal.Decimal(str(time.time()))
        old_games = [game for game in get_public_games() if is_too_old(game, now)]
        for game in old_games:
            set_game_private(game["game_uuid"], "false")
        return response_payload(200, [g["game_uuid"] for g in old_games])

    except Exception as err:
        raise
        return internal_error_payload(err)
