import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
import decimal
import time
from .logging import logger

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table("games")
websocket_table = dynamodb.Table("watch_game_websocket_manager")
reports_table = dynamodb.Table("nickname_reports")

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

def transact_create_rematch(new_game, prev_game_uuid):
    """
    Saves the rematch game and claims the link on the previous game in a single
    transaction. Either both land or neither does, so a failure can never leave
    the previous game pointing at a game that was not saved. Claiming the link
    is one-shot, so such a pointer would be permanent.

    Returns True on success, False if the previous game's link was already
    claimed (the caller re-reads it to find the winner).
    """
    new_game["last_modified"] = decimal.Decimal(str(time.time()))

    try:
        table.meta.client.transact_write_items(TransactItems=[
            {
                'Put': {
                    'TableName': table.name,
                    'Item': new_game,
                    'ConditionExpression': 'attribute_not_exists(game_uuid)'
                }
            },
            {
                'Update': {
                    'TableName': table.name,
                    'Key': {'game_uuid': prev_game_uuid},
                    'UpdateExpression': "SET next_game_uuid = :n, last_modified = :t",
                    'ConditionExpression': "attribute_not_exists(next_game_uuid) OR attribute_type(next_game_uuid, :null_type)",
                    'ExpressionAttributeValues': {
                        ':n': new_game["game_uuid"],
                        ':t': decimal.Decimal(str(time.time())),
                        ':null_type': 'NULL'
                    }
                }
            }
        ])
        return True

    except ClientError as e:
        if e.response['Error']['Code'] == 'TransactionCanceledException':
            logger.warning(f"Rematch registration lost the race for game {prev_game_uuid}.")
            return False
        else:
            raise