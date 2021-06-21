import boto3


def query_dynamodb():
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table("games")
    response = table.scan()
    return response['Items']


def lambda_handler(event, context):
    games = query_dynamodb()
    games_info = [{"uuid": game["game_uuid"], "started": game["status"] != "Not started", "players": [p["nickname"] for p in game["players"]]} for game in games]
    return games_info
