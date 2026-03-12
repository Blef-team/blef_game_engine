from collections import defaultdict
from random import sample, shuffle, choice, randint
from itertools import islice, product, permutations
from math import floor
import time
import decimal
import copy
import uuid
from .db import table, save_in_dynamodb, transact_end_of_round
from .time_limit import send_time_limit_message
from .logging import logger
from .constants import GameStatus, CommonCardsRules, RuleValues

def create_player(game, nickname):
    players = game.get("players")
    ready = False if len(players) == 0 or game.get("rules", {}).get("time_limit", RuleValues.TIME_LIMIT_DEFAULT) != RuleValues.TIME_LIMIT_NO_LIMIT else True
    return {
        "uuid": str(uuid.uuid4()), 
        "nickname": nickname, 
        "n_cards": 0, 
        "ready": ready,
        "team": None
    }

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

def get_team(game, nickname):
    p = get_player_by_nickname(game["players"], nickname)
    return p.get("team") if p else None

def censor_game(game, player_nickname=None):
    lose_round_id = get_action_ids(game.get("rules", {}))["lose_round"]

    req_team = get_team(game, player_nickname) if player_nickname else None

    # If the round is lost, reveal all active hands
    if any(event.get("action_id") == lose_round_id for event in game.get("history", [])):
        revealed_hands = [hand for hand in game["hands"] if is_active_player(game["players"], hand["nickname"])]
    else: # Otherwise, reveal own hand + teammates' hands
        revealed_hands = []
        for hand in game["hands"]:
            if not is_active_player(game["players"], hand["nickname"]):
                continue
            if hand["nickname"] == player_nickname or (req_team is not None and get_team(game, hand["nickname"]) == req_team):
                revealed_hands.append(hand)

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

def calculate_common_cards(players, rules):
    common_cards_rule = int(rules.get("common_cards", RuleValues.COMMON_CARDS_DEFAULT))
    if common_cards_rule in (CommonCardsRules.INCREASING.value, CommonCardsRules.SLOWLY_INCREASING.value):
        rule_enum = CommonCardsRules(common_cards_rule)
        extra_cards_per_hand = [hs-1 for hs in [int(p.get("n_cards")) for p in players] if hs>0]
        return int(1 + sum(extra_cards_per_hand) * rule_enum.rate)
    else:
        return common_cards_rule

def draw_cards(players, rules):
    """
    Draws cards for players and common cards based on the provided rules.
    """
    deck_size = rules.get("deck_size", RuleValues.DECK_SIZE_DEFAULT)
    num_jokers = int(rules.get("jokers", RuleValues.JOKERS_DEFAULT))
    num_blanks = int(rules.get("blanks", RuleValues.BLANKS_DEFAULT))
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

def seat_teams(team_counts):
    """
    Brute-force solver that guarantees optimal seating, but randomises 
    team priority, equivalent arrangements, and table rotation to ensure fairness.
    """
    players = []
    for team, count in team_counts.items():
        players.extend([team] * count)
    
    total_seats = len(players)
        
    # Randomisation 1: Break alphabetical bias. Shuffle the teams first
    teams_list = list(team_counts.items())
    shuffle(teams_list) 

    # Sort teams by:
    # 1. Size descending (optimise the most constrained teams first)
    # 2. Actual teams > Dummy teams (x[0] > 0 evaluates to True/1 for actual, False/0 for dummy)
    # 3. Random tie-breaker (preserved by Python's stable sort from the shuffle above)    
    sorted_teams = sorted(teams_list, key=lambda x: (x[1], x[0] > 0), reverse=True)
    team_order = [t[0] for t in sorted_teams]
    
    unique_arrangements = set(permutations(players))
    
    # Randomisation 2: Pool the winning orders and choose one at random
    best_arrangements = []
    best_score = None
    
    # Evaluate every possible table
    for arr in unique_arrangements:
        team_indices = {t: [] for t in team_order}
        for i, t in enumerate(arr):
            team_indices[t].append(i)
            
        global_max_clump = 0
        team_gap_tuples = []
        
        # Calculate stats for each team in order of size
        for team in team_order:
            indices = team_indices[team]
            count = len(indices)
            
            if count == 0:
                continue
            if count == 1:
                global_max_clump = max(global_max_clump, 1)
                team_gap_tuples.append((total_seats,)) # Infinite gap for independents
                continue
                
            # Calculate gaps between consecutive players
            gaps = []
            for i in range(count - 1):
                gaps.append(indices[i+1] - indices[i])
            gaps.append(total_seats - indices[-1] + indices[0]) # Wrap-around gap (last player to first player)
            
            # Calculate the largest clump for this specific team
            max_clump = 1
            current_clump = 1
            for i in range(count * 2): # Loop twice through the gaps to easily handle wrap-around clumps
                if gaps[i % count] == 1:
                    current_clump += 1
                    max_clump = max(max_clump, current_clump)
                else:
                    current_clump = 1
            max_clump = min(max_clump, count) # Cap it (prevents infinite loop logic overshoot if team occupies whole table)
            global_max_clump = max(global_max_clump, max_clump)

            team_gap_tuples.append(tuple(sorted(gaps))) # Add this team's sorted gap distribution to the scoring list
            
        # Construct the score tuple
        # Priority 1: Minimise the largest clump anywhere on the table
        # Priority 2: Maximise Team 1's gap distribution, then Team 2's gap distribution etc.
        score = (-global_max_clump, *team_gap_tuples)
        
        if best_score is None or score > best_score:
            best_score = score
            best_arrangements = [arr]
        elif score == best_score:
            best_arrangements.append(arr)
            
    winning_arrangement = list(choice(best_arrangements))
    
    # Randomisation 3: Randomise the starting player (shift the entire array by a random number of seats)
    shift = randint(0, total_seats - 1)
    final_table = winning_arrangement[shift:] + winning_arrangement[:shift]
            
    return final_table

def arrange_players(players):
    # Shuffle players first so that within teams players are distributed randomly 
    shuffle(players)
        
    players_by_team = defaultdict(list)
    
    for p in players:
        team = p.get("team")
        # Treat independent players as special dummy teams to space them out
        if team is None or team == 0: 
            if p.get("ai_agent"):
                players_by_team[-2].append(p) # Group all independent AIs into dummy team -2
            else:
                players_by_team[-1].append(p) # Group all independent Humans into dummy team -1
        else:
            players_by_team[team].append(p)
            
    # Build the team_counts dictionary expected by the solver
    team_counts = {team_id: len(members) for team_id, members in players_by_team.items()}
    
    # Get the optimal seating sequence of team IDs
    optimal_sequence = seat_teams(team_counts)
    
    # Map the sequence of team IDs back to the actual player objects
    final_players = []
    for team_id in optimal_sequence:
        final_players.append(players_by_team[team_id].pop(0))
        
    return final_players

def start_player_timer(game):
    """
    Checks for a time limit, sends an SQS message if active,
    and returns the calculated move deadline.
    """
    rules = game.get("rules", {})
    time_limit = int(rules.get("time_limit", RuleValues.TIME_LIMIT_NO_LIMIT))
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
    base_deck_size = int(rules.get("deck_size", RuleValues.DECK_SIZE_DEFAULT))
    jokers = int(rules.get("jokers", RuleValues.JOKERS_DEFAULT))
    blanks = int(rules.get("blanks", RuleValues.BLANKS_DEFAULT))
    if jokers > 0:
        suggested_total = (base_deck_size + blanks + jokers) / (1 + 0.2 * (jokers + 1))
        return min(floor(suggested_total), base_deck_size)
    else:
        return base_deck_size
        

def calculate_largest_feasible_max_cards_per_player(n_players, total_cards_in_play, common_cards_rule):
    """Calculates the theoretical maximum number of cards a single player can hold."""
    # x*n + 1 + floor((x-1)*n*rate) <= deck_size  ->  x*n + 1 + (x-1)*n*rate < deck_size + 1  ->   x*n + x*n*rate - n*rate < deck_size  ->
    # x*n*(1+rate) < deck_size + n*rate  ->  x < (deck_size + n*rate) / (n * (1+rate))  ->  x = int((deck_size + n*rate) / (n * (1+rate)) - epsilon)

    if common_cards_rule in CommonCardsRules.special_values():
        rate = CommonCardsRules(common_cards_rule).rate
        # Formula rearranged to solve for x (max_cards): x <= (total_cards - 1 + n*rate) / (n * (1 + rate))
        max_cards = (total_cards_in_play + n_players * rate) / (n_players * (1 + rate)) - 0.001
        return min(floor(max_cards), 11)
    else:
        max_cards = (total_cards_in_play - common_cards_rule) / n_players
        return min(floor(max_cards), 11)

def calculate_actual_max_cards(rules, n_players):
    if n_players < 2:
        return 0
    common_cards_rule = int(rules.get("common_cards", RuleValues.COMMON_CARDS_DEFAULT))
    max_cards_preference = rules.get("max_cards_preference", RuleValues.MAX_CARDS_NO_PREFERENCE_INTERNAL)
    total_deck_size = int(rules.get("deck_size", RuleValues.DECK_SIZE_DEFAULT)) + int(rules.get("jokers", RuleValues.JOKERS_DEFAULT)) + int(rules.get("blanks", RuleValues.BLANKS_DEFAULT))
    if max_cards_preference:
        return min(int(max_cards_preference), calculate_largest_feasible_max_cards_per_player(n_players, total_deck_size, common_cards_rule))
    else:
        suggested_total_cards_in_round = calculate_suggested_max_cards_dealt_in_any_round(rules)
        return calculate_largest_feasible_max_cards_per_player(n_players, suggested_total_cards_in_round, common_cards_rule)

def start_game(game):
    game_uuid = game["game_uuid"]
    players = game["players"]
    rules = game.get("rules", {})

    for player in players:
        player["n_cards"] = 1

    public = "false"
    status = GameStatus.RUNNING
    round_number = 1
    
    players = arrange_players(players)
    hands, common_hand = draw_cards(players, rules)
    cp_nickname = players[0]["nickname"]

    game['round_number'] = round_number
    game['cp_nickname'] = cp_nickname
    move_deadline = start_player_timer(game)

    table.update_item(
        Key={'game_uuid': game_uuid},
        UpdateExpression="set last_modified = :last_modified, players = :players, #game_public = :public, #game_status = :status, round_number = :round_number, hands = :hands, common_hand = :common_hand, cp_nickname = :cp_nickname, move_deadline = :move_deadline",
        ExpressionAttributeValues={
            ':last_modified': decimal.Decimal(str(time.time())),
            ':players': players,
            ':public': public,
            ':status': status,
            ':round_number': round_number,
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
    return True

def start_next_round(game):
    """
    Recalls the loser of the previous round, updates cards,
    and starts the next round with the correct current player.
    """
    # Update the card counts for the new round
    losing_player_nickname = find_losing_player_nickname(game)    
    losing_player = get_player_by_nickname(game["players"], losing_player_nickname)
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
    game["status"] = GameStatus.RUNNING
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
    deck_size = rules.get("deck_size", RuleValues.DECK_SIZE_DEFAULT)
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
    time_limit = int(game.get("rules", {}).get("time_limit", RuleValues.TIME_LIMIT_NO_LIMIT))

    game["history"].append({"player": losing_player_nickname, "action_id": action_ids["lose_round"]})
    game["cp_nickname"] = None
    game["move_deadline"] = None

    # 1. Prepare the archive state
    archive_state = copy.deepcopy(game)
    archive_state["game_uuid"] = f"{game['game_uuid']}_{game['round_number']}"

    # 2. Prepare the next live state
    # Use a temporary copy to determine the outcome without changing the state prematurely.
    temp_players = update_n_cards(game, losing_player_nickname)
    
    if sum(1 for p in temp_players if p.get("n_cards", 0) > 0) <= 1:
        # Game is finished
        game["status"] = GameStatus.FINISHED
        game["players"] = temp_players # Use the updated player list
        if transact_end_of_round(game, archive_state, original_last_modified):
            return archive_state
    elif time_limit > 0:
        # Game is timed and waiting for human players' readiness
        game["status"] = GameStatus.WAITING_FOR_READY
        game["players"] = unset_human_readiness(game["players"])
        if transact_end_of_round(game, archive_state, original_last_modified):
            return game
    else:
        # No finish and no time limit: save archive state unconditionally and start the next round
        save_in_dynamodb(archive_state)
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


def update_n_cards(game, losing_player_nickname):
    temp_players = copy.deepcopy(game["players"])
    losing_player_obj = get_player_by_nickname(temp_players, losing_player_nickname)
    losing_player_obj["n_cards"] += 1
    if losing_player_obj["n_cards"] > game["max_cards"]:
        losing_player_obj["n_cards"] = 0
    return temp_players


def find_losing_player_nickname(game):
    action_ids = get_action_ids(game.get("rules", {}))
    losing_player_nickname = None
    for event in reversed(game.get("history", [])):
        if event.get("action_id") == action_ids["lose_round"]:
            losing_player_nickname = event.get("player")
            break
    return losing_player_nickname

def is_update_redundant(game):
    """
    Detects game state updates that are duplicates or will be obsolete within milliseconds
    """
    is_snapshot = "_" in game.get("game_uuid", "")
    is_timed_game = game.get("rules", {}).get("time_limit", RuleValues.TIME_LIMIT_NO_LIMIT) != RuleValues.TIME_LIMIT_NO_LIMIT
    losing_player_nickname = find_losing_player_nickname(game)

    # At the end of timed rounds, the archival snapshot and the live state are the same, so skip the snapshot.
    # Except in the last round, where the live state shows the finished game information
    if is_snapshot and is_timed_game and losing_player_nickname:
        updated_players = update_n_cards(game, losing_player_nickname)
        if sum(1 for p in updated_players if p.get("n_cards", 0) > 0) > 1:
            return True
    
    # When the last player gets ready, the game state will be updated but the next round will start immediately.
    # This makes the state with every player ready obsolete within milliseconds
    if not is_snapshot and is_timed_game and losing_player_nickname and not game.get("status") == GameStatus.FINISHED:
        if all(p.get("ready", False) for p in game.get("players", [])):
            return True

    return False
