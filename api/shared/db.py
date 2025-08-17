import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
import decimal
import time
from .logging import logger

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table("games")
websocket_table = dynamodb.Table("watch_game_websocket_manager")

def get_from_dynamodb(game_uuid):
    response = table.query(KeyConditionExpression=Key('game_uuid').eq(game_uuid))
    items = response.get("Items")
    if len(items) == 1:
        return items[0]
    return None

def save_in_dynamodb(obj, game_uuid=None, last_modified_condition=None):
    if game_uuid:
        obj['game_uuid'] = game_uuid
    obj["last_modified"] = decimal.Decimal(str(time.time()))

    put_params = {'Item': obj}
    if last_modified_condition:
        put_params['ConditionExpression'] = "last_modified = :lm"
        put_params['ExpressionAttributeValues'] = {':lm': last_modified_condition}

    try:
        table.put_item(**put_params)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            logger.warning(f"Conditional save failed for game_uuid: {obj.get('game_uuid')}.")
            return False
        else:
            raise

def transact_end_of_round(live_game_state, archive_game_state, last_modified_condition):
    """
    Atomically updates the live game state and saves the round archive using a transaction.
    Returns True on success, False if the transaction fails due to a condition check.
    """
    try:
        archive_game_state['last_modified'] = decimal.Decimal(str(time.time()))
        live_game_state['last_modified'] = decimal.Decimal(str(time.time()))
        
        transact_items = [
            {
                'Put': {
                    'TableName': table.name,
                    'Item': live_game_state,
                    'ConditionExpression': 'last_modified = :lm',
                    'ExpressionAttributeValues': {':lm': last_modified_condition}
                }
            },
            {
                'Put': {
                    'TableName': table.name,
                    'Item': archive_game_state,
                    'ConditionExpression': 'attribute_not_exists(game_uuid)'
                }
            }
        ]
        table.meta.client.transact_write_items(TransactItems=transact_items)
        
        return True

    except ClientError as e:
        if e.response['Error']['Code'] == 'TransactionCanceledException':
            logger.warning(f"End of round transaction failed for game {live_game_state['game_uuid']} due to a race condition.")
            return False
        else:
            raise