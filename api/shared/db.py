import boto3
import logging
import time
import decimal
import json
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError # Ensure ClientError is imported

# Initialize logger (assuming basicConfig is called elsewhere or Lambda provides one)
logger = logging.getLogger()
logger.setLevel(logging.INFO) # Set default level

# Initialize DynamoDB client (consider making table name configurable)
DYNAMODB_TABLE_NAME = "games" # Or use os.environ.get("DYNAMODB_TABLE_NAME", "games")
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

# Deserializer for DynamoDB stream events
deserializer = boto3.dynamodb.types.TypeDeserializer()

class DecimalEncoder(json.JSONEncoder):
    """ Helper class to convert a DynamoDB item to JSON, handling Decimals. """
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            # Check if it's an integer
            if obj % 1 == 0:
                return int(obj)
            else:
                return float(obj)
        # Let the base class default method raise the TypeError
        return super(DecimalEncoder, self).default(obj)

def get_game_from_db(game_uuid):
    """ Fetches a single game item from DynamoDB by game_uuid. """
    try:
        response = table.query(KeyConditionExpression=Key('game_uuid').eq(game_uuid))
        items = response.get("Items")
        if items and len(items) == 1:
            return items[0]
        logger.warning(f"Game not found in DB for UUID: {game_uuid}")
        return None
    except ClientError as e:
        logger.exception(f"DynamoDB ClientError getting game {game_uuid}: {e.response['Error']['Message']}")
        raise # Re-raise after logging specific error
    except Exception as e:
        logger.exception(f"Unexpected error getting game {game_uuid}")
        raise

def save_game_to_db(game_data):
    """ Saves or overwrites a game item in DynamoDB. Adds/updates last_modified. """
    try:
        game_data["last_modified"] = decimal.Decimal(str(time.time()))
        table.put_item(Item=game_data)
        logger.info(f"Successfully saved/overwrote game {game_data.get('game_uuid')}")
        return True
    except ClientError as e:
        logger.exception(f"DynamoDB ClientError saving game {game_data.get('game_uuid')}: {e.response['Error']['Message']}")
        return False # Return False on DB error
    except Exception as e:
        logger.exception(f"Unexpected error saving game {game_data.get('game_uuid')}")
        return False

# Alias for clarity when overwriting
overwrite_game = save_game_to_db

def update_game_in_db(game_uuid, update_expression, expression_attribute_values, expression_attribute_names=None):
    """ Updates an existing game item in DynamoDB. Always adds/updates last_modified. """
    try:
        # Ensure last_modified is always updated
        # Use a placeholder not likely to clash with input values
        timestamp_placeholder = ':_last_modified_timestamp'
        expression_attribute_values[timestamp_placeholder] = decimal.Decimal(str(time.time()))
        # Append last_modified update (use alias if 'last_modified' could be a name conflict)
        update_expression_final = f"{update_expression}, last_modified = {timestamp_placeholder}"

        params = {
            'Key': {'game_uuid': game_uuid},
            'UpdateExpression': update_expression_final,
            'ExpressionAttributeValues': expression_attribute_values,
            'ReturnValues': "NONE"
        }
        if expression_attribute_names:
            params['ExpressionAttributeNames'] = expression_attribute_names

        table.update_item(**params)
        logger.info(f"Successfully updated game {game_uuid}")
        return True
    except ClientError as e:
        logger.exception(f"DynamoDB ClientError updating game {game_uuid}: {e.response['Error']['Message']}")
        return False # Return False on DB error
    except Exception as e:
        logger.exception(f"Unexpected error updating game {game_uuid}")
        return False

def update_game_public_status(game_uuid, is_public):
    """ Sets the public status ('true'/'false' string) of a game. """
    return update_game_in_db(
        game_uuid=game_uuid,
        update_expression="set #game_public = :public",
        expression_attribute_values={':public': "true" if is_public else "false"},
        expression_attribute_names={'#game_public': "public"} # Alias for reserved word
    )

def update_game_players(game_uuid, players, admin_nickname=None):
    """ Updates the players list and optionally the admin nickname for a game. """
    update_expr = "set players = :players"
    expr_values = {':players': players}
    if admin_nickname is not None:
         update_expr += ", admin_nickname = :admin_nickname"
         expr_values[':admin_nickname'] = admin_nickname

    return update_game_in_db(
        game_uuid=game_uuid,
        update_expression=update_expr,
        expression_attribute_values=expr_values
    )

def query_public_games(projection_expression=None, filter_expression=None):
    """ Queries the public-index GSI for games marked as public='true'. """
    items = []
    try:
        params = {
            'IndexName': "public-index", # Assumes GSI named 'public-index'
            'KeyConditionExpression': Key('public').eq("true")
        }
        if projection_expression:
            params['ProjectionExpression'] = projection_expression
        if filter_expression:
             params['FilterExpression'] = filter_expression

        response = table.query(**params)
        items.extend(response.get('Items', []))

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            logger.info("Paginating query_public_games...")
            params['ExclusiveStartKey'] = response['LastEvaluatedKey']
            response = table.query(**params)
            items.extend(response.get('Items', []))

        logger.info(f"Query public games found {len(items)} items.")
        return items
    except ClientError as e:
        logger.exception(f"DynamoDB ClientError querying public games: {e.response['Error']['Message']}")
        return [] # Return empty list on error
    except Exception as e:
        logger.exception("Unexpected error querying public games")
        return []

def get_recently_active_public_games(max_age_seconds=1800):
    """ Gets public games modified within the last max_age_seconds. """
    now = decimal.Decimal(str(time.time()))
    # Ensure game_uuid is the standard 36-char UUID (not historical)
    # and last_modified is greater than threshold
    filter_expr = Attr('game_uuid').size().eq(36) & Attr('last_modified').gt(now - max_age_seconds)
    return query_public_games(filter_expression=filter_expr)

def get_public_games_for_cleanup():
     """ Gets public games (only game_uuid, last_modified) for cleanup task. """
     return query_public_games(projection_expression="game_uuid,last_modified")

def deserialise_dynamodb_stream_event(dynamodb_image):
    """ Converts a DynamoDB stream image (NewImage/OldImage) to a regular Python dict. """
    if not dynamodb_image:
        return {}
    try:
        # Uses the deserializer initialized at the top of the file
        return {k: deserializer.deserialize(v) for k, v in dynamodb_image.items()}
    except Exception as e:
        logger.error(f"Error deserializing DynamoDB stream image: {e}")
        logger.debug(f"Image data: {dynamodb_image}")
        return {} # Return empty dict on error


def update_game_play(game_uuid, cp_nickname, history):
    """ Updates the game state after a regular play action (cp_nickname, history). """
    update_expression = "set cp_nickname = :cp_nickname, history = :history"
    expression_attribute_values = {
        ':cp_nickname': cp_nickname,
        ':history': history
    }
    # update_game_in_db automatically adds last_modified
    return update_game_in_db(
        game_uuid=game_uuid,
        update_expression=update_expression,
        expression_attribute_values=expression_attribute_values
    )

def save_historical_game(game_data):
     """ Saves a completed round's game state with a modified game_uuid (game_uuid_round). """
     try:
        # Ensure required fields are present
        if not all(k in game_data for k in ('game_uuid', 'round_number')):
             logger.error("Missing game_uuid or round_number for historical save.")
             return False

        # Ensure round_number is int for suffix
        round_num = int(game_data['round_number'])
        historical_uuid = f"{game_data['game_uuid']}_{round_num}"
        historical_game_data = game_data.copy()
        historical_game_data['game_uuid'] = historical_uuid

        # Use save_game_to_db which handles put_item and last_modified
        success = save_game_to_db(historical_game_data)
        if success:
            logger.info(f"Saved historical game state: {historical_uuid}")
        else:
            logger.error(f"Failed to save historical game state via save_game_to_db: {historical_uuid}")
        return success

     except ValueError:
         logger.error(f"Invalid round_number for historical save: {game_data.get('round_number')}")
         return False
     except Exception as e:
        logger.exception(f"Error saving historical game {game_data.get('game_uuid')}")
        return False