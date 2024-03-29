import uuid
import boto3
from boto3.dynamodb.conditions import Key
import time
import json
from math import floor
from random import shuffle, sample, choice
from itertools import islice, product
import decimal


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


def request_error_payload(request, message=None):
    body = "Bad request payload: '{}'".format(request)
    if message:
        body = "{}\n{}".format(body, message)
    return error_payload(400, body)


def parameter_error_payload(param_key, param_value, message=None):
    body = "Bad input value in '{}': {}".format(param_key, param_value)
    if message:
        body = "{}\n{}".format(body, message)
    return error_payload(400, body)


def parse_event(event):
    # Basic input validation
    if not isinstance(event, dict):
        return False

    # Handle both direct triggers and API Gateway
    body = event.get("body", event)
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError:
            return None
    path_params = event.get("pathParameters", {})
    query_params = event.get("queryStringParameters", {})
    body.update(path_params)
    body.update(query_params)
    return body


def is_valid_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def draw_cards(players):
    possible_cards = product(range(6), range(4))
    all_cards_raw = sample(list(possible_cards), sum(int(p["n_cards"]) for p in players))
    all_cards = [{"value": tup[0], "colour": tup[1]} for tup in all_cards_raw]
    card_iterator = iter(all_cards)
    hands = []
    for player in players:
        player_hand = list(islice(card_iterator, 0, int(player["n_cards"])))
        hands.append({"nickname": player['nickname'], "hand": player_hand})
    return hands


def arrange_players(players):
    """
        Order the human and AI players
        for optimal gameplay
    """
    num_total = len(players)
    num_ais = sum(1 for p in players if p.get("ai_agent"))
    offset = choice(range(num_total))

    ai_positions_from_zero = [floor(i * num_total / num_ais) for i in range(num_ais)]
    ai_positions = [(i + offset) % num_total for i in ai_positions_from_zero]
    ai_players = [p for p in players if p.get("ai_agent")]

    human_players = [p for p in players if not p.get("ai_agent")]
    shuffle(human_players)

    players = []

    for i in range(num_total):
        if i in ai_positions and ai_players:
            players.append(ai_players.pop(0))
        elif human_players:
            players.append(human_players.pop(0))

    return players


def get_from_dynamodb(game_uuid):
    response = table.query(KeyConditionExpression=Key('game_uuid').eq(game_uuid))
    items = response.get("Items")
    if len(items) == 1:
        return items[0]
    return None


def update_in_dynamodb(game_uuid, public, status, round_number, max_cards, players, hands, cp_nickname):
    table.update_item(
        Key={
            'game_uuid': game_uuid
        },
        UpdateExpression="set last_modified = :last_modified, players = :players, #game_public = :public, #game_status = :status, round_number = :round_number, max_cards = :max_cards, hands = :hands, cp_nickname = :cp_nickname",
        ExpressionAttributeValues={
            ':last_modified': decimal.Decimal(str(time.time())),
            ':players': players,
            ':public': public,
            ':status': status,
            ':round_number': round_number,
            ':max_cards': max_cards,
            ':hands': hands,
            ':cp_nickname': cp_nickname
        },
        ExpressionAttributeNames={
            '#game_public': "public",
            '#game_status': "status"
        },
        ReturnValues="NONE"
    )
    return True


def lambda_handler(event, context):
    try:
        body = parse_event(event)
        if not body:
            return request_error_payload(event)

        game_uuid = str(body.get("game_uuid"))
        if not is_valid_uuid(game_uuid):
            return parameter_error_payload("game_uuid", game_uuid, message="Invalid game UUID")

        game = get_from_dynamodb(game_uuid)
        if not game:
            return parameter_error_payload("game_uuid", game_uuid, message="Game does not exist")

        if game.get("status") != "Not started":
            return error_payload(403, "Game already started")

        admin_uuid = str(body.get("admin_uuid"))

        if not admin_uuid:
            return parameter_error_payload("admin_uuid", admin_uuid, message="Admin UUID missing - please supply it")

        if not is_valid_uuid(admin_uuid):
            return parameter_error_payload("admin_uuid", admin_uuid, message="Invalid admin UUID")

        players = game.get("players")
        game_admin_uuid = [player["uuid"] for player in players if player["nickname"] == game.get("admin_nickname")][0]
        if game_admin_uuid != admin_uuid:
            return parameter_error_payload("admin_uuid", admin_uuid, message="Admin UUID does not match")

        n_players = len(game.get("players", []))
        if n_players < 2:
            return error_payload(403, "At least 2 players needed to start a game")

        public = "false"
        status = "Running"
        round_number = 1
        max_cards = 11
        if n_players > 2:
            max_cards = floor(24 / n_players)

        for player in players:
            player["n_cards"] = 1
        players = arrange_players(players)

        hands = draw_cards(players)

        cp_nickname = players[0]["nickname"]

        update_in_dynamodb(game_uuid, public, status, round_number, max_cards, players, hands, cp_nickname)

        return response_payload(202, {"message": "Game started"})

    except Exception as err:
        return internal_error_payload(err)
