import uuid
import boto3
import time


def save_in_dynamodb(obj):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table("games")
    obj["last_modified"] = round(time.time())
    table.put_item(Item=obj)
    return True


def lambda_handler(event, context):
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
        return {"game_uuid": game_uuid}
