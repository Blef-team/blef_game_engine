from random import sample, shuffle, choice
from itertools import islice, product
from math import floor
import time
import decimal
import copy
from .db import table, save_in_dynamodb
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

def get_revealed_hands(game, current_round, current_status, player_authenticated, player_nickname):
    revealed_hands = []
    if game["round_number"] < current_round or current_status in ["Finished", "Waiting for ready"]:
        revealed_hands = [hand for hand in game["hands"] if is_active_player(game["players"], hand["nickname"])]
    elif player_authenticated and game["round_number"] == current_round:
        revealed_hands = [hand for hand in game["hands"] if is_active_player(game["players"], hand["nickname"]) and hand["nickname"] == player_nickname]
    return revealed_hands

def censor_game(game, current_round, player_authenticated, player_nickname):
    revealed_hands = get_revealed_hands(game, current_round, game["status"], player_authenticated, player_nickname)

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
        "rules": game.get("rules", {})
    }

def calculate_common_cards(players, rules):
    common_cards_rule = int(rules.get("common_cards", 0))
    if common_cards_rule == -1:
        return min(int(p.get("n_cards", 1)) for p in players)
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
    """Checks for a time limit and sends an SQS message if active."""
    rules = game.get("rules", {})
    time_limit = int(rules.get("time_limit", 0))
    logger.info(f"## Checking for game {game.get('game_uuid')}")
    logger.info(f"## Time limit rule is {time_limit} and current player is {game.get('cp_nickname')}")
    
    if time_limit > 0 and game.get("cp_nickname"):
        player_to_time = get_player_by_nickname(game.get("players", []), game.get("cp_nickname"))
        if player_to_time:
            history_len = len(game.get("history", []))
            logger.info(f"START_PLAYER_TIMER: Scheduling timeout for {player_to_time['nickname']} with history length {history_len}")
            send_time_limit_message(
                game["game_uuid"],
                player_to_time["uuid"],
                game["round_number"],
                time_limit,
                history_len
            )

def start_game(game):
    game_uuid = game["game_uuid"]
    players = game["players"]
    rules = game.get("rules", {})
    n_players = len(players)
    deck_size = rules.get("deck_size", 24)
    common_cards_rule = int(rules.get("common_cards", 0))

    for player in players:
        player["n_cards"] = 1

    num_common_cards = calculate_common_cards(players, rules)

    numerator = deck_size - num_common_cards if common_cards_rule > 0 else deck_size
    denominator = n_players + 1 if common_cards_rule == -1 else n_players
    max_cards = floor(numerator / denominator)
    if max_cards > 11: max_cards = 11

    public = "false"
    status = "Running"
    round_number = 1
    
    players = arrange_players(players)
    hands, common_hand = draw_cards(players, rules)
    cp_nickname = players[0]["nickname"]

    table.update_item(
        Key={'game_uuid': game_uuid},
        UpdateExpression="set last_modified = :last_modified, players = :players, #game_public = :public, #game_status = :status, round_number = :round_number, max_cards = :max_cards, hands = :hands, common_hand = :common_hand, cp_nickname = :cp_nickname",
        ExpressionAttributeValues={
            ':last_modified': decimal.Decimal(str(time.time())),
            ':players': players,
            ':public': public,
            ':status': status,
            ':round_number': round_number,
            ':max_cards': max_cards,
            ':hands': hands,
            ':common_hand': common_hand,
            ':cp_nickname': cp_nickname
        },
        ExpressionAttributeNames={
            '#game_public': "public",
            '#game_status': "status"
        }
    )

    game['round_number'] = round_number
    game['cp_nickname'] = cp_nickname
    start_player_timer(game)
    return True

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
    save_in_dynamodb(game)
    
    start_player_timer(game)
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
    Handles all the logic for ending a round. If a time limit is active,
    it puts the game into a "Waiting for ready" state instead of starting the next round.
    """
    action_ids = get_action_ids(game.get("rules", {}))
    game["history"].append({"player": losing_player_nickname, "action_id": action_ids["lose_round"]})
    game["cp_nickname"] = None
    end_of_round_state = copy.deepcopy(game)
    save_in_dynamodb(end_of_round_state, f"{end_of_round_state['game_uuid']}_{int(end_of_round_state['round_number'])}")

    # Check for game end condition *before* altering the live state
    temp_players = copy.deepcopy(game["players"])
    temp_losing_player = get_player_by_nickname(temp_players, losing_player_nickname)
    temp_losing_player["n_cards"] += 1
    if temp_losing_player["n_cards"] > game["max_cards"]:
        temp_losing_player["n_cards"] = 0
    
    active_players = sum(1 for p in temp_players if p["n_cards"] > 0)
    if active_players <= 1:
        game["status"] = "Finished"
        game["players"] = temp_players
        save_in_dynamodb(game)
        return end_of_round_state

    # If game is not over, decide the next step
    active_human_players = [p for p in temp_players if p.get("n_cards") > 0 and not p.get("ai_agent")]
    time_limit = int(game.get("rules", {}).get("time_limit", 0))
    if time_limit > 0 and active_human_players:
        game["status"] = "Waiting for ready"
        game["players"] = unset_human_readiness(game["players"])
        save_in_dynamodb(game)
        return game # For timed games, return the waiting state
    else:
        # If no time limit, start the next round immediately but return the snapshot
        start_next_round(game)
        return end_of_round_state

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
