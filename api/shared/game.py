from random import sample, shuffle, choice
from itertools import islice, product
from math import floor
import time
import decimal
import copy
from .db import table, save_in_dynamodb, transact_end_of_round
from .time_limit import send_time_limit_message
from .logging import logger

def get_player_by_nickname(players, nickname):
    filtered_players = [p for p in players if p["nickname"] == nickname]
    if filtered_players and filtered_players[0]:
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

def find_next_active_player(players, cp_nickname):
    active_players = [player for player in players if player["n_cards"] != 0 or player["nickname"] == cp_nickname]
    current_player_order = [i for i, player in enumerate(active_players) if player["nickname"] == cp_nickname][0]
    next_active_player = (active_players * 2)[current_player_order + 1]
    return next_active_player

def censor_game(game, current_round, player_nickname=None):
    revealed_hands = []
    if game["status"] == "Finished":
        revealed_hands = game["hands"]
    elif game["round_number"] < current_round or game["status"] == "Waiting for ready":
        revealed_hands = [hand for hand in game["hands"] if is_active_player(game["players"], hand["nickname"])]
    elif player_nickname and game["round_number"] == current_round:
        revealed_hands = [hand for hand in game["hands"] if is_active_player(game["players"], hand["nickname"]) and hand["nickname"] == player_nickname]

    private_players = []
    for player in game["players"]:
        private_players.append({key: player[key] for key in player if key != "uuid"})

    return {
        "admin_nickname": game["admin_nickname"],
        "public": game["public"],
        "room": game["room"],
        "status": game["status"],
        "round_number": game["round_number"],
        "max_cards": game["max_cards"],
        "players": private_players,
        "hands": revealed_hands,
        "common_hand": game.get("common_hand", []),
        "cp_nickname": game["cp_nickname"],
        "history": game["history"],
        "last_modified": game["last_modified"],
        "rules": game.get("rules", {}),
        "move_deadline": game.get("move_deadline"),
        "update_time": time.time()
    }

def get_common_cards_rate_by_id(rule):
    if rule == -2:
        return 1/5
    if rule == -1:
        return 1/3
    return False

def calculate_common_cards(players, rules):
    common_cards_rule = int(rules.get("common_cards", 0))
    if common_cards_rule in (-1, -2):
        extra_cards_per_hand = [hs-1 for hs in [int(p.get("n_cards")) for p in players] if hs>0]
        rate = get_common_cards_rate_by_id(common_cards_rule)
        return int(1 + sum(extra_cards_per_hand) * rate)
    else:
        return common_cards_rule

def draw_cards(players, rules):
    """
    Draws cards for players and common cards based on the provided rules.
    """
    deck_size = rules.get("deck_size", 24)
    num_jokers = int(rules.get("jokers", 0))
    num_blanks = int(rules.get("blanks", 0))
    num_common_cards = calculate_common_cards(players, rules)

    if deck_size == 32:
        possible_cards = product(range(8), range(4))
    else:
        possible_cards = product(range(6), range(4))

    full_deck_raw = list(possible_cards)
    full_deck_raw.extend([(-1, -1)] * num_jokers)
    full_deck_raw.extend([(-2, -2)] * num_blanks)
    
    total_cards_to_deal = sum(int(p["n_cards"]) for p in players) + num_common_cards
    all_cards_raw = sample(full_deck_raw, total_cards_to_deal)

    all_cards = [{"value": tup[0], "colour": tup[1]} for tup in all_cards_raw]
    card_iterator = iter(all_cards)
    hands = []
    for player in players:
        player_hand = list(islice(card_iterator, 0, int(player["n_cards"])))
        hands.append({"nickname": player['nickname'], "hand": player_hand})

    common_hand = list(islice(card_iterator, 0, num_common_cards))
    return hands, common_hand

def arrange_players(players):
    num_total = len(players)
    num_ais = sum(1 for p in players if p.get("ai_agent"))
    if num_ais == 0:
        shuffle(players)
        return players
        
    offset = choice(range(num_total))
    ai_positions_from_zero = [floor(i * num_total / num_ais) for i in range(num_ais)]
    ai_positions = [(i + offset) % num_total for i in ai_positions_from_zero]
    ai_players = [p for p in players if p.get("ai_agent")]
    human_players = [p for p in players if not p.get("ai_agent")]
    shuffle(human_players)
    
    final_players = []
    for i in range(num_total):
        if i in ai_positions and ai_players:
            final_players.append(ai_players.pop(0))
        elif human_players:
            final_players.append(human_players.pop(0))
    return final_players

def start_player_timer(game):
    """
    Checks for a time limit, sends an SQS message if active,
    and returns the calculated move deadline.
    """
    rules = game.get("rules", {})
    time_limit = int(rules.get("time_limit", 0))
    logger.info(f"## Checking for game {game.get('game_uuid')}")
    logger.info(f"## Time limit rule is {time_limit} and current player is {game.get('cp_nickname')}")
    
    if time_limit > 0 and game.get("cp_nickname"):
        player_to_time = get_player_by_nickname(game.get("players", []), game.get("cp_nickname"))
        if player_to_time:
            history_len = len(game.get("history", []))
            send_time_limit_message(
                game["game_uuid"],
                player_to_time["uuid"],
                game["round_number"],
                time_limit,
                history_len
            )
            return decimal.Decimal(str(time.time() + time_limit))
    return None


def calculate_suggested_max_cards_dealt_in_any_round(rules):
    """
    Calculates the suggested total number of cards to be in play for optimal experience.
    Computes the expanded deck size and applies a downward adjustment for jokers. 
    Always caps the final result at base deck size to not prolong the game
    """
    base_deck_size = int(rules.get("deck_size", 24))
    jokers = int(rules.get("jokers", 0))
    blanks = int(rules.get("blanks", 0))
    if jokers > 0:
        suggested_total = (base_deck_size + blanks + jokers) / (1 + 0.2 * (jokers + 1))
        return min(floor(suggested_total), base_deck_size)
    else:
        return base_deck_size
        

def calculate_largest_allowed_max_cards_per_player(n_players, total_cards_in_play, common_cards_rule):
    """Calculates the theoretical maximum number of cards a single player can hold."""
    # x*n + 1 + floor((x-1)*n*rate) <= deck_size  ->  x*n + 1 + (x-1)*n*rate < deck_size + 1  ->   x*n + x*n*rate - n*rate < deck_size  ->
    # x*n*(1+rate) < deck_size + n*rate  ->  x < (deck_size + n*rate) / (n * (1+rate))  ->  x = int((deck_size + n*rate) / (n * (1+rate)) - epsilon)

    if common_cards_rule in (-1, -2):
        rate = get_common_cards_rate_by_id(common_cards_rule)
        # Formula rearranged to solve for x (max_cards): x <= (total_cards - 1 + n*rate) / (n * (1 + rate))
        max_cards = (total_cards_in_play + n_players * rate) / (n_players * (1 + rate)) - 0.001
        return min(floor(max_cards), 11)
    else:
        max_cards = (total_cards_in_play - common_cards_rule) / n_players
        return min(floor(max_cards), 11)

def start_game(game):
    game_uuid = game["game_uuid"]
    players = game["players"]
    rules = game.get("rules", {})
    n_players = len(players)

    # Determine the final max_cards value
    custom_max_cards = int(game.get("max_cards", 0))
    deck_size = int(rules.get("deck_size", 24))
    jokers = int(rules.get("jokers", 0))
    blanks = int(rules.get("blanks", 0))
    common_cards_rule = int(rules.get("common_cards", 0))

    if custom_max_cards == 0: # Auto-calculate
        suggested_total = calculate_suggested_max_cards_dealt_in_any_round(rules)
        max_cards = calculate_largest_allowed_max_cards_per_player(n_players, suggested_total, common_cards_rule)
    else: # Validate and use custom value
        theoretical_max = calculate_largest_allowed_max_cards_per_player(n_players, deck_size + jokers + blanks, common_cards_rule)
        if custom_max_cards > theoretical_max:
            return {
                "success": False,
                "error": "MAX_CARDS_TOO_HIGH",
                "message": f"With {n_players} players, max cards cannot exceed {theoretical_max}. Please adjust rules."
            }
        else:
            max_cards = custom_max_cards

    for player in players:
        player["n_cards"] = 1

    public = "false"
    status = "Running"
    round_number = 1
    
    players = arrange_players(players)
    hands, common_hand = draw_cards(players, rules)
    cp_nickname = players[0]["nickname"]

    game['round_number'] = round_number
    game['cp_nickname'] = cp_nickname
    move_deadline = start_player_timer(game)

    table.update_item(
        Key={'game_uuid': game_uuid},
        UpdateExpression="set last_modified = :last_modified, players = :players, #game_public = :public, #game_status = :status, round_number = :round_number, max_cards = :max_cards, hands = :hands, common_hand = :common_hand, cp_nickname = :cp_nickname, move_deadline = :move_deadline",
        ExpressionAttributeValues={
            ':last_modified': decimal.Decimal(str(time.time())),
            ':players': players,
            ':public': public,
            ':status': status,
            ':round_number': round_number,
            ':max_cards': max_cards,
            ':hands': hands,
            ':common_hand': common_hand,
            ':cp_nickname': cp_nickname,
            ':move_deadline': move_deadline
        },
        ExpressionAttributeNames={
            '#game_public': "public",
            '#game_status': "status"
        }
    )
    return {"success": True}

def start_next_round(game):
    """
    Recalls the loser of the previous round, updates cards,
    and starts the next round with the correct current player.
    """
    action_ids = get_action_ids(game.get("rules", {}))
    losing_player_nickname = None
    # Find the loser from the history
    for event in reversed(game.get("history", [])):
        if event.get("action_id") == action_ids["lose_round"]:
            losing_player_nickname = event.get("player")
            break
    
    losing_player = get_player_by_nickname(game["players"], losing_player_nickname)

    # Update the card counts for the new round
    if losing_player:
        losing_player["n_cards"] += 1
        if losing_player["n_cards"] > game["max_cards"]:
            losing_player["n_cards"] = 0 # Player is now eliminated
    
    # Set the next player
    if losing_player["n_cards"] == 0:
        game["cp_nickname"] = find_next_active_player(game["players"], losing_player_nickname)["nickname"]
    else:
        game["cp_nickname"] = losing_player["nickname"]

    # Set up and save the next round
    game["status"] = "Running"
    game["round_number"] += 1
    game["history"] = []
    game["hands"], game["common_hand"] = draw_cards(game["players"], game.get("rules", {}))
    
    game["move_deadline"] = start_player_timer(game)
    
    save_in_dynamodb(game)
    return True

def get_action_ids(rules):
    """
    Returns a dictionary of key action IDs based on the deck size.
    """
    deck_size = rules.get("deck_size", 24)
    if deck_size == 32:
        return {"check": 140, "lose_round": 141}
    return {"check": 88, "lose_round": 89}

def end_round(game, losing_player_nickname):
    """
    Atomically handles the end of a round using a DynamoDB transaction.
    Returns the archived game state on success, or False if the transaction fails.
    """
    original_last_modified = game.get("last_modified")
    action_ids = get_action_ids(game.get("rules", {}))
    time_limit = int(game.get("rules", {}).get("time_limit", 0))

    # 1. Prepare the archive state
    archive_state = copy.deepcopy(game)
    archive_state["game_uuid"] = f"{game['game_uuid']}_{game['round_number']}"
    archive_state["history"].append({"player": losing_player_nickname, "action_id": action_ids["lose_round"]})
    archive_state["cp_nickname"] = None
    archive_state["move_deadline"] = None

    # 2. Prepare the next live state
    # Use a temporary copy to determine the outcome without changing the state prematurely.
    temp_players = copy.deepcopy(game["players"])
    losing_player_obj = get_player_by_nickname(temp_players, losing_player_nickname)
    if losing_player_obj:
        losing_player_obj["n_cards"] += 1
        if losing_player_obj["n_cards"] > game["max_cards"]:
            losing_player_obj["n_cards"] = 0
    active_players_count = sum(1 for p in temp_players if p.get("n_cards", 0) > 0)
    
    if active_players_count <= 1:
        # Game is finished
        next_live_state = copy.deepcopy(game)
        next_live_state["status"] = "Finished"
        next_live_state["players"] = temp_players # Use the updated player list
        next_live_state["history"] = []
        next_live_state["cp_nickname"] = None
        next_live_state["move_deadline"] = None
        if transact_end_of_round(next_live_state, archive_state, original_last_modified):
            return archive_state
    elif time_limit > 0 and any(p for p in game["players"] if p.get("n_cards") > 0 and not p.get("ai_agent")):
        # Game is timed and will wait for players
        next_live_state = copy.deepcopy(archive_state) # Start from the archive state
        next_live_state["game_uuid"] = game["game_uuid"] # Reset the UUID to the live one
        next_live_state["status"] = "Waiting for ready"
        next_live_state["players"] = unset_human_readiness(next_live_state["players"])
        if transact_end_of_round(next_live_state, archive_state, original_last_modified):
            return archive_state
    else:
        # No finish and no time limit: save archive state unconditionally and start the next round
        save_in_dynamodb(archive_state)
        game["history"] = archive_state["history"]
        start_next_round(game)
        return archive_state

    return False # This is only reached if a transaction fails

def unset_human_readiness(players):
    """
    Sets the 'ready' status of all human players in a list to False.
    """
    for player in players:
        if not player.get("ai_agent"):
            player["ready"] = False
    return players

def is_game_about_to_finish(game_state):
    """
    Predicts if the game will end after this round.
    """
    action_ids = get_action_ids(game_state.get("rules", {}))
    losing_player_nickname = None
    for event in reversed(game_state.get("history", [])):
        if event.get("action_id") == action_ids["lose_round"]:
            losing_player_nickname = event.get("player")
            break

    if not losing_player_nickname:
        return False

    temp_players = copy.deepcopy(game_state["players"])
    losing_player = get_player_by_nickname(temp_players, losing_player_nickname)

    if not losing_player:
        return False

    losing_player["n_cards"] += 1
    if losing_player["n_cards"] > game_state["max_cards"]:
        losing_player["n_cards"] = 0

    active_players = sum(1 for p in temp_players if p.get("n_cards", 0) > 0)
    return active_players <= 1
