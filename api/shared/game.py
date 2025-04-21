import logging
from random import sample, shuffle, choice
from itertools import islice, product
from math import floor
import time
import decimal # Keep if game_logic needs Decimal

logger = logging.getLogger()

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

_INDEXATION_CACHE = None

# Load agent mapping from environment variables if needed (e.g., for invite_aiagent)
# AGENT_MAPPING = json.loads(os.environ.get("agent_mapping", "{}"))
# logger = logging.getLogger() # Setup logging if needed

def get_player_by_nickname(players, nickname):
    """ Finds a player dictionary in a list by nickname. """
    if not players or not nickname:
        return None
    return next((p for p in players if p.get("nickname") == nickname), None)

def get_player_by_uuid(players, player_uuid):
    """ Finds a player dictionary in a list by UUID. """
    if not players or not player_uuid:
        return None
    return next((p for p in players if p.get("uuid") == player_uuid), None)

def get_nickname_by_uuid(players, player_uuid):
    """ Finds a player's nickname by their UUID. """
    player = get_player_by_uuid(players, player_uuid)
    return player.get("nickname") if player else None

def is_active_player(players, nickname):
    """ Checks if a player (by nickname) is active (has cards). """
    player = get_player_by_nickname(players, nickname)
    # Assumes active means having n_cards > 0. Adjust if logic differs.
    return player and player.get("n_cards", 0) > 0

def get_aiagent_player_uuid(game):
    """ Gets the UUID of the current player if they are an AI agent. """
    current_player_nickname = game.get("cp_nickname")
    if not current_player_nickname:
        return None
    player_obj = get_player_by_nickname(game.get("players", []), current_player_nickname)
    # Check if the player has an 'ai_agent' key indicating they are AI
    if player_obj and player_obj.get("ai_agent"):
        return player_obj.get("uuid")
    return None # Current player is not an AI or not found

def get_aiagent_type(game):
     """ Gets the type/name of the AI agent for the current player. """
     current_player_nickname = game.get("cp_nickname")
     if not current_player_nickname:
         return None
     player_obj = get_player_by_nickname(game.get("players", []), current_player_nickname)
     return player_obj.get("ai_agent") if player_obj else None


def is_legal_action(action, history):
    """ Checks if an action ID is legal given the game history. """
    # Validate action range (assuming 0-87 are normal bids, 88 is 'call')
    if not isinstance(action, int) or action < 0 or action > 88:
        return False
    # If no history, cannot call '88'. First bid cannot be '88'.
    if not history:
        return action != 88
    # If history exists, the new action must be greater than the last action_id
    # and cannot be 'call' (88) if the last action was already 'call'.
    last_action = history[-1].get("action_id")
    if last_action == 88: # Cannot bid after a call
        return False
    return action == 88 or action > last_action # Allow call or higher bid

def format_ai_nickname(base_name, existing_nicknames):
    """ Generates a unique AI nickname (e.g., Agent_1_(AI), Agent_2_(AI)). """
    i = 0
    while True:
        formatted_name = f"{base_name}_{i+1}" if i > 0 else base_name
        final_name = f"{formatted_name}_(AI)"
        if final_name not in existing_nicknames:
            return final_name
        i += 1

def censor_game_state(game, requesting_player_uuid=None):
    """
    Creates a view of the game state suitable for returning to a client.
    Hides sensitive information like other players' UUIDs and hands,
    unless the request is authenticated for a specific player during their turn/round.
    """
    if not game:
        return None

    current_round = game.get("round_number", 0)
    current_status = game.get("status")
    all_players = game.get("players", [])
    all_hands = game.get("hands", [])

    requesting_player_nickname = get_nickname_by_uuid(all_players, requesting_player_uuid) if requesting_player_uuid else None
    is_authenticated_player = bool(requesting_player_nickname)

    # Censor player list (remove UUIDs)
    censored_players = []
    for player in all_players:
        censored_player = {k: v for k, v in player.items() if k != 'uuid'}
        censored_players.append(censored_player)

    # Determine which hands to reveal
    revealed_hands = []
    # Reveal all active hands if game/round is finished
    if current_status == "Finished": # Assuming "Finished" means end of game
         revealed_hands = [
             hand for hand in all_hands
             if is_active_player(all_players, hand.get("nickname"))
         ]
    # Reveal only the authenticated player's hand if the round is ongoing
    elif is_authenticated_player and current_status == "Running":
        revealed_hands = [
            hand for hand in all_hands
            if hand.get("nickname") == requesting_player_nickname and is_active_player(all_players, hand.get("nickname"))
        ]
    # In other states (Not started, potentially between rounds), reveal no hands.

    # Build the visible game state
    visible_game = {
        "admin_nickname": game.get("admin_nickname"),
        "public": game.get("public"),
        "room": game.get("room"),
        "status": current_status,
        "round_number": current_round,
        "max_cards": game.get("max_cards"),
        "players": censored_players, # Use censored list
        "hands": revealed_hands,     # Use revealed list
        "cp_nickname": game.get("cp_nickname"),
        "history": game.get("history", []),
        "last_modified": game.get("last_modified") # Keep for client-side checks maybe
    }
    return visible_game

def is_game_too_old(game_metadata, max_age_seconds=600):
     """ Checks if a game's last_modified timestamp is too old. """
     now = decimal.Decimal(str(time.time()))
     last_modified = game_metadata.get("last_modified")
     if not isinstance(last_modified, decimal.Decimal):
         return True # Treat missing or invalid timestamp as old
     return (now - last_modified) > max_age_seconds

def load_indexation():
    """ Loads and caches the action indexation from the CSV constant. """
    global _INDEXATION_CACHE
    if _INDEXATION_CACHE is not None:
        return _INDEXATION_CACHE

    header = None
    indexation = []
    lines = INDEXATION_CSV.strip().split("\n")
    if not lines:
        _INDEXATION_CACHE = []
        return _INDEXATION_CACHE

    header = lines[0].split(",")
    for line in lines[1:]:
        if not line.strip(): continue
        try:
             action_id_str, set_type, detail_1, detail_2 = line.split(",")
             indexation.append({
                 "action_id": int(action_id_str), # Store as int
                 "set_type": set_type,
                 "detail_1": detail_1,
                 "detail_2": detail_2
             })
        except ValueError as e:
             logger.error(f"Error parsing indexation line: '{line}'. Error: {e}")
             # Handle error appropriately, maybe skip line or raise

    _INDEXATION_CACHE = indexation
    logger.info("Action indexation loaded and cached.")
    return _INDEXATION_CACHE

def determine_set_existence(cards, action_id):
    """ Checks if a claimed set (by action_id) exists in the provided list of cards. """
    try:
        action_id = int(action_id)
        indexation = load_indexation()
        if action_id < 0 or action_id >= len(indexation):
             logger.error(f"Invalid action_id {action_id} for indexation lookup.")
             return False # Or raise error

        set_row = indexation[action_id]
        set_type = set_row["set_type"]
        # Convert details to int only when needed, handle empty strings
        detail_1_str = set_row["detail_1"]
        detail_2_str = set_row["detail_2"]

        card_values = [card["value"] for card in cards]
        card_colours = [card["colour"] for card in cards]

        # --- Logic based on set_type ---
        if set_type == "High card":
            detail_1 = int(detail_1_str)
            return card_values.count(detail_1) >= 1
        elif set_type == "Pair":
            detail_1 = int(detail_1_str)
            return card_values.count(detail_1) >= 2
        elif set_type == "Two pairs":
            detail_1 = int(detail_1_str)
            detail_2 = int(detail_2_str)
            return card_values.count(detail_1) >= 2 and card_values.count(detail_2) >= 2
        elif set_type == "Small straight": # 0-1-2-3-4
            return all(v in card_values for v in range(5))
        elif set_type == "Big straight": # 1-2-3-4-5
            return all(v in card_values for v in range(1, 6))
        elif set_type == "Great straight": # 0-1-2-3-4-5 (all 6 values)
             # This seems unlikely with standard poker dice, adjust if needed
             return all(v in card_values for v in range(6))
        elif set_type == "Three of a kind":
            detail_1 = int(detail_1_str)
            return card_values.count(detail_1) >= 3
        elif set_type == "Full house":
            detail_1 = int(detail_1_str) # The three
            detail_2 = int(detail_2_str) # The pair
            return card_values.count(detail_1) >= 3 and card_values.count(detail_2) >= 2
        elif set_type == "Colour":
            detail_1 = int(detail_1_str)
            return card_colours.count(detail_1) >= 5 # Needs 5 cards of specified colour
        elif set_type == "Four of a kind":
            detail_1 = int(detail_1_str)
            return card_values.count(detail_1) >= 4
        # Flushes (Straights of the same color)
        elif set_type in ("Small flush", "Big flush", "Great flush"):
             detail_1 = int(detail_1_str) # The required colour
             relevant_cards = [card for card in cards if card["colour"] == detail_1]
             if len(relevant_cards) < 5: # Need at least 5 cards of the colour
                 return False
             relevant_values = [card["value"] for card in relevant_cards]
             if set_type == "Small flush":
                 return all(v in relevant_values for v in range(5))
             elif set_type == "Big flush":
                 return all(v in relevant_values for v in range(1, 6))
             elif set_type == "Great flush":
                  # Again, seems unlikely unless rules differ
                 return all(v in relevant_values for v in range(6))
        else:
             logger.error(f"Unknown set_type '{set_type}' in indexation.")
             return False

    except ValueError as e:
         logger.error(f"Value error processing action_id {action_id} or details: {e}")
         return False # Treat conversion errors as non-existent set
    except IndexError:
         logger.error(f"Index error looking up action_id {action_id}.")
         return False
    except Exception as err:
        logger.exception(f"Unexpected error in determine_set_existence for action_id {action_id}")
        raise # Re-raise unexpected errors

def find_next_active_player(players, current_player_nickname):
    """ Finds the next player in order who is still active (n_cards > 0). """
    active_players = [p for p in players if p.get("n_cards", 0) > 0]
    if not active_players:
        return None # No active players left

    try:
        # Find the index of the current player *within the original players list*
        current_index_orig = next(i for i, p in enumerate(players) if p.get("nickname") == current_player_nickname)
    except StopIteration:
        logger.error(f"Current player {current_player_nickname} not found in player list.")
        # Fallback: return the first active player? Or raise error?
        return active_players[0] if active_players else None

    # Iterate through the original list starting from the next player, wrapping around
    num_players = len(players)
    for i in range(1, num_players + 1):
        next_index_orig = (current_index_orig + i) % num_players
        next_player = players[next_index_orig]
        # Check if this next player is active
        if next_player.get("n_cards", 0) > 0:
            return next_player

    # Should not happen if there's at least one active player, but as fallback:
    logger.warning("Could not find next active player logically, returning first active.")
    return active_players[0]


def draw_cards(players):
    """ Draws cards for all active players based on their n_cards count. """
    active_players = [p for p in players if p.get("n_cards", 0) > 0]
    total_cards_needed = sum(int(p["n_cards"]) for p in active_players)

    # Define the deck (e.g., 6 values, 4 colours = 24 poker dice faces)
    # Adjust if using standard cards
    possible_cards = list(product(range(6), range(4))) # 0-5 values, 0-3 colours

    if total_cards_needed > len(possible_cards):
        # Handle error: Not enough cards in the 'deck'
        logger.error(f"Cannot draw {total_cards_needed} cards; only {len(possible_cards)} available.")
        # Raise an exception or return empty hands?
        raise ValueError("Not enough unique cards available to draw.")

    # Sample unique cards from the deck
    drawn_cards_raw = sample(possible_cards, total_cards_needed)
    drawn_cards = [{"value": tup[0], "colour": tup[1]} for tup in drawn_cards_raw]
    card_iterator = iter(drawn_cards)

    hands = []
    for player in players: # Iterate through original list to maintain order/structure
         if player.get("n_cards", 0) > 0:
             player_hand = list(islice(card_iterator, 0, int(player["n_cards"])))
             hands.append({"nickname": player['nickname'], "hand": player_hand})
         else:
             # Add entry for inactive player with empty hand? Or omit?
             # Omitting seems cleaner for game state unless needed elsewhere
             # hands.append({"nickname": player['nickname'], "hand": []})
             pass
    return hands


def arrange_players(players):
    """
    Arranges players, attempting to intersperse AI and human players.
    Returns a new list with players in the arranged order.
    """
    num_total = len(players)
    if num_total <= 1:
        return list(players) # No arranging needed for 0 or 1 player

    ai_players = [p for p in players if p.get("ai_agent")]
    human_players = [p for p in players if not p.get("ai_agent")]
    num_ais = len(ai_players)
    num_humans = len(human_players)

    # Simple shuffle if only one type of player
    if num_ais == 0 or num_humans == 0:
        shuffled_players = list(players)
        shuffle(shuffled_players)
        return shuffled_players

    # Try to intersperse
    arranged_players = []
    offset = choice(range(num_total)) # Random starting position offset
    ai_indices = set((floor(i * num_total / num_ais) + offset) % num_total for i in range(num_ais))

    # Shuffle human players for randomness among them
    shuffle(human_players)

    ai_iter = iter(ai_players)
    human_iter = iter(human_players)

    for i in range(num_total):
        if i in ai_indices:
            try:
                 arranged_players.append(next(ai_iter))
            except StopIteration: # Should not happen if counts match
                 logger.warning("Ran out of AI players unexpectedly during arrangement.")
                 arranged_players.append(next(human_iter)) # Fill with human instead
        else:
             try:
                arranged_players.append(next(human_iter))
             except StopIteration: # Should not happen
                logger.warning("Ran out of human players unexpectedly during arrangement.")
                arranged_players.append(next(ai_iter)) # Fill with AI instead

    return arranged_players

def get_aiagent_player_uuid_from_stream(game_data):
    """ Gets AI agent UUID from game data (potentially from stream). """
    cp_nickname = game_data.get("cp_nickname")
    if not cp_nickname:
        return None
    player = get_player_by_nickname(game_data.get("players", []), cp_nickname)
    return player.get("uuid") if player and player.get("ai_agent") else None
