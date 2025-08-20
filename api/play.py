import time
import decimal
import os
import boto3
from botocore.exceptions import ClientError
from itertools import combinations
from shared.response import *
from shared.db import table, get_from_dynamodb
from shared.api_gateway import parse_event
from shared.logging import logger
from shared.game import get_nickname_by_uuid, censor_game, find_next_active_player, end_round, start_player_timer, get_action_ids
from shared.inputs import is_valid_uuid

sqs_client = boto3.client("sqs")
TIME_LIMIT_QUEUE_NAME = os.environ.get("time_limit_queue_name")

def get_set_details_from_action_id(action_id, deck_size=24):
    """
    Determines the set type and details from the action_id and deck size.
    """
    action_id = int(action_id)
    # Define base parameters based on deck size
    if deck_size == 24:
        vals = 6
        straight_types = {
            "Small straight": list(range(5)),
            "Big straight": list(range(1, 6)),
            "Great straight": list(range(6)),
        }
        flush_straight_types = straight_types
    else:  # deck_size == 32
        vals = 8
        straight_types = {f"Straight {i+1}": list(range(i, i + 5)) for i in range(4)}
        flush_straight_types = {f"Straight flush {i+1}": list(range(i, i + 5)) for i in range(4)}

    # Dynamically calculate the boundaries for each set type
    current_boundary = 0
    boundaries = {}
    boundaries["High card"] = current_boundary + vals
    current_boundary = boundaries["High card"]
    boundaries["Pair"] = current_boundary + vals
    current_boundary = boundaries["Pair"]
    boundaries["Two pairs"] = current_boundary + (vals * (vals - 1)) // 2
    current_boundary = boundaries["Two pairs"]
    boundaries["Straight"] = current_boundary + len(straight_types)
    current_boundary = boundaries["Straight"]
    boundaries["Three of a kind"] = current_boundary + vals
    current_boundary = boundaries["Three of a kind"]
    boundaries["Full house"] = current_boundary + (vals * (vals - 1))
    current_boundary = boundaries["Full house"]
    boundaries["Flush"] = current_boundary + 4
    current_boundary = boundaries["Flush"]
    boundaries["Four of a kind"] = current_boundary + vals
    current_boundary = boundaries["Four of a kind"]
    boundaries["Straight flush"] = current_boundary + (len(flush_straight_types) * 4)
    current_boundary = boundaries["Straight flush"]

    if action_id < boundaries["High card"]:
        return {"set_type": "High card", "detail_1": action_id}
    if action_id < boundaries["Pair"]:
        return {"set_type": "Pair", "detail_1": action_id - boundaries["High card"]}
    if action_id < boundaries["Two pairs"]:
        offset = action_id - boundaries["Pair"]
        pairs = list(combinations(reversed(range(vals)), 2))
        pair_index = len(pairs) - 1 - offset
        d1, d2 = pairs[pair_index]
        return {"set_type": "Two pairs", "detail_1": d1, "detail_2": d2}
    if action_id < boundaries["Straight"]:
        offset = action_id - boundaries["Two pairs"]
        set_name, details = list(straight_types.items())[offset]
        return {"set_type": set_name, "details": details}
    if action_id < boundaries["Three of a kind"]:
        return {"set_type": "Three of a kind", "detail_1": action_id - boundaries["Straight"]}
    if action_id < boundaries["Full house"]:
        offset = action_id - boundaries["Three of a kind"]
        d1 = offset // (vals - 1)
        d2 = offset % (vals - 1)
        if d2 >= d1: d2 += 1
        return {"set_type": "Full house", "detail_1": d1, "detail_2": d2}
    if action_id < boundaries["Flush"]:
        return {"set_type": "Flush", "detail_1": action_id - boundaries["Full house"]}
    if action_id < boundaries["Four of a kind"]:
        return {"set_type": "Four of a kind", "detail_1": action_id - boundaries["Flush"]}
    if action_id < boundaries["Straight flush"]:
        offset = action_id - boundaries["Four of a kind"]
        suit = offset % 4
        straight_type_index = offset // 4
        set_name, details = list(flush_straight_types.items())[straight_type_index]
        # Rename to a generic "Straight flush" for the check logic
        return {"set_type": "Straight flush", "detail_1": suit, "details": details}

    return None # Should not be reached with a valid action_id

def check_high_card(cards, value, num_jokers):
    return cards.count(value) + num_jokers >= 1

def check_pair(cards, value, num_jokers):
    return cards.count(value) + num_jokers >= 2

def check_two_pairs(cards, value1, value2, num_jokers):
    jokers_needed_for_value1 = max(0, 2 - cards.count(value1))
    jokers_needed_for_value2 = max(0, 2 - cards.count(value2))
    return (jokers_needed_for_value1 + jokers_needed_for_value2) <= num_jokers

def check_straight(cards, required_values, num_jokers):
    unique_cards = set(cards)
    missing_cards = 0
    for value in required_values:
        if value not in unique_cards:
            missing_cards += 1
    return missing_cards <= num_jokers

def check_three_of_a_kind(cards, value, num_jokers):
    return cards.count(value) + num_jokers >= 3

def check_full_house(cards, value1, value2, num_jokers):
    jokers_needed_for_value1 = max(0, 3 - cards.count(value1))
    jokers_needed_for_value2 = max(0, 2 - cards.count(value2))
    return (jokers_needed_for_value1 + jokers_needed_for_value2) <= num_jokers

def check_flush(cards_by_colour, colour, num_jokers):
    return cards_by_colour.get(colour, 0) + num_jokers >= 5

def check_four_of_a_kind(cards, value, num_jokers):
    return cards.count(value) + num_jokers >= 4

def check_straight_flush(cards_with_colour, colour, required_values, num_jokers):
    card_set = set(cards_with_colour)
    missing_cards = 0
    for value in required_values:
        if (value, colour) not in card_set:
            missing_cards += 1
    return missing_cards <= num_jokers

def determine_set_existence(all_cards, action_id, rules, num_jokers):
    """
    Checks if a given set exists within a list of cards, using a specified number of jokers.
    """
    try:
        set_details = get_set_details_from_action_id(action_id, rules.get("deck_size", 24))
        if not set_details:
            logger.error("Could not get set details from action_id.")
            return False
        logger.info(f"Set details from action_id: {set_details}")

        set_type = set_details["set_type"]
        detail_1 = set_details.get("detail_1")
        detail_2 = set_details.get("detail_2")
        details = set_details.get("details")

        card_values = [int(card["value"]) for card in all_cards if int(card["value"]) not in [-1, -2]]
        card_colours = [int(card["colour"]) for card in all_cards if int(card["colour"]) not in [-1, -2]]
        cards_with_colour = [(int(c["value"]), int(c["colour"])) for c in all_cards if int(c["value"]) not in [-1, -2]]
        cards_by_colour = {colour: card_colours.count(colour) for colour in set(card_colours)}

        if set_type == "High card":
            return check_high_card(card_values, detail_1, num_jokers)
        elif set_type == "Pair":
            return check_pair(card_values, detail_1, num_jokers)
        elif set_type == "Two pairs":
            return check_two_pairs(card_values, detail_1, detail_2, num_jokers)
        elif "straight" in set_type.lower() and "flush" not in set_type.lower():
            return check_straight(card_values, details, num_jokers)
        elif set_type == "Three of a kind":
            return check_three_of_a_kind(card_values, detail_1, num_jokers)
        elif set_type == "Full house":
            return check_full_house(card_values, detail_1, detail_2, num_jokers)
        elif set_type == "Flush":
            return check_flush(cards_by_colour, detail_1, num_jokers)
        elif set_type == "Four of a kind":
            return check_four_of_a_kind(card_values, detail_1, num_jokers)
        elif "straight flush" in set_type.lower():
            return check_straight_flush(cards_with_colour, detail_1, details, num_jokers)
        return False
    except Exception as err:
        print(f"Error in determine_set_existence: {err}")
        return False

def update_in_dynamodb(game_uuid, cp_nickname, history, move_deadline, last_modified):
    """
    Conditionally updates the game state in DynamoDB.
    Returns True on success, False on failure (due to race condition).
    """
    try:
        table.update_item(
            Key={'game_uuid': game_uuid},
            UpdateExpression="SET last_modified = :t, cp_nickname = :c, history = :h, move_deadline = :d",
            ConditionExpression="last_modified = :lm",
            ExpressionAttributeValues={
                ':t': decimal.Decimal(str(time.time())),
                ':c': cp_nickname,
                ':h': history,
                ':d': move_deadline,
                ':lm': last_modified
            }
        )
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            logger.warning("Failed to update game state due to a race condition (play vs timeout).")
            return False
        else:
            raise

def handle_check(game):
    """
    Gathers all necessary data and calls the determine_set_existence and end_round functions.
    """
    rules = game.get("rules", {})
    history = game.get("history", [])
    
    # Identify the checked bet and player
    better_nickname = history[-2]["player"]
    action_id_being_checked = history[-2]["action_id"]

    # Gather all cards from all players and the common hand
    all_cards = [card for hand in game.get("hands", []) for card in hand.get("hand", [])]
    all_cards.extend(game.get("common_hand", []))
    
    # Calculate the number of usable jokers
    better_hand_obj = next((hand for hand in game.get("hands", []) if hand.get("nickname") == better_nickname), None)
    better_hand = better_hand_obj.get("hand", []) if better_hand_obj else []
    common_hand = game.get("common_hand", [])
    num_jokers = sum(1 for card in better_hand if int(card.get("value")) == -1)
    num_jokers += sum(1 for card in common_hand if int(card.get("value")) == -1)

    # Call the evaluation function
    set_exists = determine_set_existence(all_cards, action_id_being_checked, rules, num_jokers)

    losing_player_nickname = history[-1]["player"] if set_exists else better_nickname

    return end_round(game, losing_player_nickname)

def lambda_handler(event, context):
    try:
        body = parse_event(event)
        if not body:
            return request_error_payload(event)

        game_uuid = str(body.get("game_uuid"))
        if not is_valid_uuid(game_uuid):
            return parameter_error_payload("game_uuid", game_uuid, "Invalid game UUID")

        game = get_from_dynamodb(game_uuid)
        if not game:
            return parameter_error_payload("game_uuid", game_uuid, "Game does not exist")
        if game.get("status") != "Running":
            return error_payload(400, "This game is not currently running")

        player_uuid = str(body.get("player_uuid"))
        player_nickname = get_nickname_by_uuid(game["players"], player_uuid)
        if not player_nickname or player_nickname != game["cp_nickname"]:
            return parameter_error_payload("player_uuid", player_uuid, "Not your turn or invalid player UUID")

        action_id = body.get("action_id")
        try:
            action_id = int(action_id)
        except (ValueError, TypeError):
            return parameter_error_payload("action_id", action_id, "Action ID must be an integer")

        rules = game.get("rules", {})
        action_ids = get_action_ids(rules)
        check_action = action_ids["check"]

        if not (0 <= action_id <= check_action):
            return parameter_error_payload("action_id", action_id, f"Action ID must be between 0 and {check_action}")

        last_action_id = game["history"][-1]["action_id"] if game.get("history") else -1

        if action_id == check_action:
            if last_action_id == -1:
                return error_payload(400, "Cannot check as the first action of a round.")
        elif action_id <= last_action_id:
            return error_payload(400, "Action must be of a higher rank")

        game["history"].append({"player": player_nickname, "action_id": action_id})

        if action_id != check_action:
            game["cp_nickname"] = find_next_active_player(game["players"], game["cp_nickname"])["nickname"]
            game["move_deadline"] = start_player_timer(game)
            if not update_in_dynamodb(game_uuid, game["cp_nickname"], game["history"], game["move_deadline"], game["last_modified"]):
                return error_payload(409, "The game state changed.")
            return response_payload(200, censor_game(game, player_nickname))

        else:
            end_round_state = handle_check(game)
            if not end_round_state:
                return error_payload(409, "The game state changed.")
            return response_payload(200, censor_game(end_round_state, player_nickname))

    except Exception as err:
        return internal_error_payload(err)
