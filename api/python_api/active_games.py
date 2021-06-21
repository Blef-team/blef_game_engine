import boto3
from boto3.dynamodb.conditions import Attr
import time


def query_dynamodb():
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table("games")
    now = round(time.time())
    diff = 1800
    response = table.scan(
        FilterExpression=Attr('last_modified').gt(now - diff)
    )
    return response['Items']


def lambda_handler(event, context):
    items = query_dynamodb()
    return {"active_games": len(items)}
