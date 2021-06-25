import uuid
import boto3
from boto3.dynamodb.conditions import Key
import time
import json
import decimal
from random import sample
from itertools import islice, product

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table("games")

INDEXATION_CSV = """action_id,set_type,detail_1,detail_2
0,High card,0,
1,High card,1,
2,High card,2,
3,High card,3,
4,High card,4,
5,High card,5,
6,Pair,0,
7,Pair,1,
8,Pair,2,
9,Pair,3,
10,Pair,4,
11,Pair,5,
12,Two pairs,1,0
13,Two pairs,2,0
14,Two pairs,2,1
15,Two pairs,3,0
16,Two pairs,3,1
17,Two pairs,3,2
18,Two pairs,4,0
19,Two pairs,4,1
20,Two pairs,4,2
21,Two pairs,4,3
22,Two pairs,5,0
23,Two pairs,5,1
24,Two pairs,5,2
25,Two pairs,5,3
26,Two pairs,5,4
27,Small straight,,
28,Big straight,,
29,Great straight,,
30,Three of a kind,0,
31,Three of a kind,1,
32,Three of a kind,2,
33,Three of a kind,3,
34,Three of a kind,4,
35,Three of a kind,5,
36,Full house,0,1
37,Full house,0,2
38,Full house,0,3
39,Full house,0,4
40,Full house,0,5
41,Full house,1,0
42,Full house,1,2
43,Full house,1,3
44,Full house,1,4
45,Full house,1,5
46,Full house,2,0
47,Full house,2,1
48,Full house,2,3
49,Full house,2,4
50,Full house,2,5
51,Full house,3,0
52,Full house,3,1
53,Full house,3,2
54,Full house,3,4
55,Full house,3,5
56,Full house,4,0
57,Full house,4,1
58,Full house,4,2
59,Full house,4,3
60,Full house,4,5
61,Full house,5,0
62,Full house,5,1
63,Full house,5,2
64,Full house,5,3
65,Full house,5,4
66,Colour,0,
67,Colour,1,
68,Colour,2,
69,Colour,3,
70,Four of a kind,0,
71,Four of a kind,1,
72,Four of a kind,2,
73,Four of a kind,3,
74,Four of a kind,4,
75,Four of a kind,5,
76,Small flush,0,
77,Small flush,1,
78,Small flush,2,
79,Small flush,3,
80,Big flush,0,
81,Big flush,1,
82,Big flush,2,
83,Big flush,3,
84,Great flush,0,
85,Great flush,1,
86,Great flush,2,
87,Great flush,3,"""


def load_indexation():
    header = None
    indexation = []
    for line in INDEXATION_CSV.split("\n"):
        if not header:
            header = line
            continue
        action_id, set_type, detail_1, detail_2 = line.split(",")
        indexation.append({"action_id": action_id,
                           "set_type": set_type,
                           "detail_1": detail_1,
                           "detail_2": detail_2
                           })
    return indexation


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return int(obj)
        return super(DecimalEncoder, self).default(obj)


def response_payload(status_code, body):
    return {
            'statusCode': status_code,
            'body': json.dumps(body, cls=DecimalEncoder),
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


def request_error_payload(request, message=None):
    body = "Bad request payload: '{}'".format(request)
    if message:
        body = "{}\n{}".format(body, message)
    return response_payload(400, body)


def parameter_error_payload(param_key, param_value, message=None):
    body = "Bad input value in '{}': {}".format(param_key, param_value)
    if message:
        body = "{}\n{}".format(body, message)
    return response_payload(400, body)


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


def get_player_by_nickname(players, nickname):
    filtered_players = [p for p in players if p["nickname"] == nickname]
    if filtered_players:
        return filtered_players[0]


def get_nickname_by_uuid(players, player_uuid):
    filtered_players = [p for p in players if p["uuid"] == player_uuid]
    if filtered_players:
        return filtered_players[0]["nickname"]


def is_active_player(players, nickname):
    player = get_player_by_nickname(players, nickname)
    if player:
        return player["n_cards"] != 0
    return False


def get_revealed_hands(game, round, current_round, current_status, player_authenticated, player_nickname):
    revealed_hands = []
    if round < current_round or current_status == "Finished":
        revealed_hands = [hand for hand in game["hands"] if is_active_player(game["players"], hand["player"])]
    elif player_authenticated and round == current_round:
        revealed_hands = [hand for hand in game["hands"] if is_active_player(game["players"], hand["player"]) and hand["player"] == player_nickname]
    return revealed_hands


def find_next_active_player(players, cp_nickname):
    active_players = [player for player in players if player["n_cards"] != 0 or player["nickname"] == cp_nickname]
    current_player_order = [i for i, player in enumerate(active_players) if player["nickname"] == cp_nickname][0]
    next_active_player = (active_players * 2)[current_player_order + 1]
    return next_active_player


def draw_cards(players):
    possible_cards = product(range(6), range(4))
    all_cards_raw = sample(list(possible_cards), sum(int(p["n_cards"]) for p in players))
    all_cards = [{"value": tup[0], "colour": tup[1]} for tup in all_cards_raw]
    card_iterator = iter(all_cards)
    hands = []
    for player in players:
        player_hand = list(islice(card_iterator, 0, int(player["n_cards"])))
        for card in player_hand:
            card["player"] = player["nickname"]
        hands.extend(player_hand)
    return hands


def determine_set_existence(cards, action_id):
    try:
        action_id = int(action_id)
        indexation = load_indexation()
        set_row = indexation[action_id]
        set_type = set_row["set_type"]
        detail_1 = int(set_row["detail_1"]) if set_row["detail_1"] else None
        detail_2 = int(set_row["detail_2"]) if set_row["detail_2"] else None
        card_values = [card["value"] for card in cards]
        card_colours = [card["colour"] for card in cards]

        if set_type == "High card":
            return card_values.count(detail_1) >= 1
        elif set_type == "Pair":
            return card_values.count(detail_1) >= 2
        elif set_type == "Two pairs":
            return card_values.count(detail_1) >= 2 and card_values.count(detail_2) >= 2
        elif set_type == "Small straight":
            return card_values.count(0) > 0 and card_values.count(1) > 0 and card_values.count(2) > 0 and card_values.count(3) > 0 and card_values.count(4) > 0
        elif set_type == "Big straight":
            return card_values.count(1) > 0 and card_values.count(2) > 0 and card_values.count(3) > 0 and card_values.count(4) > 0 and card_values.count(5) > 0
        elif set_type == "Great straight":
            return card_values.count(0) > 0 and card_values.count(1) > 0 and card_values.count(2) > 0 and card_values.count(3) > 0 and card_values.count(4) > 0 and card_values.count(5) > 0
        elif set_type == "Three of a kind":
            return card_values.count(detail_1) >= 3
        elif set_type == "Full house":
            return card_values.count(detail_1) >= 3 and card_values.count(detail_2) >= 2
        elif set_type == "Colour":
            return card_colours.count(detail_1) >= 5
        elif set_type == "Four of a kind":
            return card_values.count(detail_1) >= 4
        elif set_type == "Small flush":
            relevant_values = [card["value"] for card in cards if card["colour"] == detail_1]
            if not relevant_values:
                return False
            return relevant_values.count(0) > 0 and relevant_values.count(1) > 0 and relevant_values.count(2) > 0 and relevant_values.count(3) > 0 and relevant_values.count(4) > 0
        elif set_type == "Big flush":
            relevant_values = [card["value"] for card in cards if card["colour"] == detail_1]
            if not relevant_values:
                return False
            return relevant_values.count(1) > 0 and relevant_values.count(2) > 0 and relevant_values.count(3) > 0 and relevant_values.count(4) > 0 and relevant_values.count(5) > 0
        elif set_type == "Great flush":
            relevant_values = [card["value"] for card in cards if card["colour"] == detail_1]
            if not relevant_values:
                return False
            return relevant_values.count(0) > 0 and relevant_values.count(1) > 0 and relevant_values.count(2) > 0 and relevant_values.count(3) > 0 and relevant_values.count(4) > 0 and relevant_values.count(5) > 0

        return False

    except Exception as err:
        raise type(err)(f"{err} \n Failed in determine_set_existence")


def get_from_dynamodb(game_uuid):
    response = table.query(KeyConditionExpression=Key('game_uuid').eq(game_uuid))
    items = response.get("Items")
    if len(items) == 1:
        return items[0]
    return None


def save_in_dynamodb(obj):
    obj["last_modified"] = round(time.time())
    table.put_item(Item=obj)
    return True


def update_in_dynamodb(game_uuid, cp_nickname, history):
    table.update_item(
        Key={
            'game_uuid': game_uuid
        },
        UpdateExpression="set last_modified = :last_modified, cp_nickname = :cp_nickname, history = :history",
        ExpressionAttributeValues={
            ':last_modified': round(time.time()),
            ':cp_nickname': cp_nickname,
            ':history': history
        },
        ReturnValues="NONE"
    )
    return True


def handle_check(game):
    cp_nickname = game["cp_nickname"]
    set_exists = determine_set_existence(game["hands"], game["history"][-2]["action_id"])
    if set_exists:
        losing_player = get_player_by_nickname(game["players"], game["history"][-1]["player"])
    else:
        losing_player = get_player_by_nickname(game["players"], game["history"][-2]["player"])

    game["history"].append({"player": losing_player["nickname"], "action_id": 89})
    game["cp_nickname"] = None

    game_uuid = game["game_uuid"]
    # Store the last round separately
    game["game_uuid"] += "_" + str(int(game['round_number']))
    if not save_in_dynamodb(game):
        raise Exception("Can't save game data")
    game["game_uuid"] = game_uuid

    losing_player["n_cards"] += 1
    # If a player surpasses max cards, make them inactive (set their n_cards to 0) and either finish the game or set up next round
    if losing_player["n_cards"] > game["max_cards"]:
        losing_player["n_cards"] = 0
        # Check if game is finished
        if sum(p["n_cards"] > 0 for p in game["players"]) == 1:
            game["status"] = "Finished"
        else:
            # If the checking player was eliminated, figure out the next player
            # Otherwise the current player doesn't change
            if losing_player["nickname"] == cp_nickname:
                game["cp_nickname"] = find_next_active_player(game["players"], cp_nickname)["nickname"]
            else:
                game["cp_nickname"] = cp_nickname
    else:
        # If no one is kicked out, picking the next player is easier
        game["cp_nickname"] = losing_player["nickname"]

    game["round_number"] += 1
    game["history"] = []
    game["hands"] = draw_cards(game["players"])

    # Overwrite the game object - for simplicity (instead of elaborate update)
    if save_in_dynamodb(game):
        return response_payload(200, {})


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

        current_status = game.get("status")

        if current_status == "Not started":
            return response_payload(400, "This game has not yet started")
        if current_status == "Finished":
            return response_payload(400, "This game has already finished")

        player_uuid = str(body.get("player_uuid"))
        if not player_uuid:
            return parameter_error_payload("player_uuid", player_uuid, message="Player UUID missing - please supply it")
        if not is_valid_uuid(player_uuid):
            return parameter_error_payload("player_uuid", player_uuid, message="Invalid player UUID")

        player_nickname = get_nickname_by_uuid(game["players"], player_uuid)
        player_authenticated = bool(player_nickname)
        is_current_player = player_nickname == game["cp_nickname"]
        if player_uuid and not player_authenticated:
            return parameter_error_payload("player_uuid", player_uuid, message="The UUID does not match any active player")
        if not is_current_player:
            return parameter_error_payload("player_uuid", player_uuid, message="The submitted UUID does not match the UUID of the current player")

        action_id = body.get("action_id")

        if not action_id:
            parameter_error_payload("action_id", action_id, message="Action ID missing - please supply it")
        if isinstance(action_id, str) and action_id.isdigit():
            action_id = int(action_id)
        elif isinstance(action_id, int):
            pass
        else:
            return parameter_error_payload("action_id", action_id)

        if action_id < 0 or action_id > 88:
            return parameter_error_payload("action_id", action_id, message="Action ID must be an integer between 0 and 88")
        elif not game["history"] and action_id == 88 or game["history"] and action_id <= game["history"][-1]["action_id"]:
            return response_payload(400, "This action not allowed right now")

        game["history"].append({"player": player_nickname, "action_id": action_id})
        
        if action_id != 88:
            cp_nickname = find_next_active_player(game["players"], game["cp_nickname"])["nickname"]
            if update_in_dynamodb(game_uuid, cp_nickname, game["history"]):
                return response_payload(200, {})
            raise Exception("Something went wrong - could not update game data")

        if action_id == 88:
            return handle_check(game)

        raise(Exception("Something went wrong - ended up with no response"))

    except Exception as err:
        raise
        return internal_error_payload(err)
