import boto3
from boto3.dynamodb.conditions import Key
import decimal
import time

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table("games")

def get_from_dynamodb(game_uuid):
    response = table.query(KeyConditionExpression=Key('game_uuid').eq(game_uuid))
    items = response.get("Items")
    if len(items) == 1:
        return items[0]
    return None

def save_in_dynamodb(obj):
    obj["last_modified"] = decimal.Decimal(str(time.time()))
    table.put_item(Item=obj)
    return True
