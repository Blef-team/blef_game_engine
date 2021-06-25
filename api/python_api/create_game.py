import uuid
import boto3
import time
import json

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


def internal_error_payload(err, message=None):
    body = "Internal Lambda function error: {}".format(err)
    if message:
        body = "{}\n{}".format(body, message)
    return response_payload(500, body)


def save_in_dynamodb(obj):
    obj["last_modified"] = round(time.time())
    table.put_item(Item=obj)
    return True


def lambda_handler(event, context):
    try:
        game_uuid = str(uuid.uuid4())
        empty_game = {
            "game_uuid": game_uuid,
            "admin_nickname": None,
            "public": False,
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
        raise
        return internal_error_payload(err)
