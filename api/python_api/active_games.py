import boto3
from boto3.dynamodb.conditions import Attr
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


def query_dynamodb():
    now = round(time.time())
    diff = 1800
    response = table.scan(
        FilterExpression=Attr('last_modified').gt(now - diff)
    )
    return response['Items']


def lambda_handler(event, context):
    try:
        items = query_dynamodb()
        return response_payload(200, {"active_games": len(items)})

    except Exception as err:
        raise
        return internal_error_payload(err)
