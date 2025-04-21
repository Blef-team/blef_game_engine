import logging
import copy

# Shared utilities using the new import style
from shared import response, input, db, game

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- Handle Check Logic ---
def handle_check_action(game_data):
    """ Handles the 'check' action (action_id 88). """
    try:
        logger.info(f"Handling 'check' action for game {game_data.get('game_uuid')}")
        cp_nickname = game_data["cp_nickname"]
        history = game_data.get("history", [])
        if len(history) < 2:
             logger.error("Handle_check called with insufficient history.")
             raise ValueError("Cannot 'check' with less than two actions in history.")

        checking_player_action = history[-1]
        previous_bid_action = history[-2]
        all_cards = [card for hand in game_data.get("hands", []) for card in hand.get("hand", [])]
        bid_action_id = previous_bid_action.get("action_id")

        # Use game module for logic
        set_exists = game.determine_set_existence(all_cards, bid_action_id)
        logger.info(f"Checking bid action {bid_action_id}. Exists in hands: {set_exists}")

        losing_player_nickname = checking_player_action.get("player") if set_exists else previous_bid_action.get("player")
        logger.info(f"Bid was {set_exists}. Player {losing_player_nickname} loses the round.")

        # Use game module
        losing_player = game.get_player_by_nickname(game_data["players"], losing_player_nickname)
        if not losing_player:
             logger.error(f"Losing player {losing_player_nickname} not found in game state!")
             raise ValueError(f"Losing player {losing_player_nickname} not found")

        game_data["history"].append({"player": losing_player_nickname, "action_id": 89}) # 89 = Loss
        game_data["cp_nickname"] = None
        end_round_game_state = copy.deepcopy(game_data)

        # Use db module
        if not db.save_historical_game(end_round_game_state):
             logger.error(f"Failed to save historical game state for round {end_round_game_state.get('round_number')}")

        losing_player["n_cards"] = losing_player.get("n_cards", 0) + 1
        max_cards = game_data.get("max_cards", 6)
        logger.info(f"Player {losing_player_nickname} now has {losing_player['n_cards']} cards (Max: {max_cards})")

        eliminated = False
        if losing_player["n_cards"] > max_cards:
            logger.info(f"Player {losing_player_nickname} is eliminated.")
            losing_player["n_cards"] = 0
            eliminated = True

        active_players = [p for p in game_data["players"] if p.get("n_cards", 0) > 0]
        if len(active_players) == 1:
            logger.info(f"Game finished! Winner: {active_players[0].get('nickname')}")
            game_data["status"] = "Finished"
            game_data["cp_nickname"] = active_players[0].get("nickname")
            game_data["hands"] = []
            # Use db module
            if not db.overwrite_game(game_data):
                 logger.error("Failed to save final game state.")
            return end_round_game_state

        game_data["round_number"] = game_data.get("round_number", 0) + 1
        game_data["history"] = []

        if eliminated:
            if losing_player_nickname == cp_nickname:
                 # Use game module
                 next_player = game.find_next_active_player(game_data["players"], cp_nickname)
                 game_data["cp_nickname"] = next_player.get("nickname") if next_player else None
            else:
                 game_data["cp_nickname"] = cp_nickname
        else:
             game_data["cp_nickname"] = losing_player_nickname

        if not game_data["cp_nickname"]:
             logger.error("Could not determine starting player for the next round.")
             if active_players: game_data["cp_nickname"] = active_players[0].get("nickname")
             else: raise ValueError("No active players left, but game didn't finish?")

        logger.info(f"Starting round {game_data['round_number']}. Player {game_data['cp_nickname']} starts.")

        # Use game module
        game_data["hands"] = game.draw_cards(game_data["players"])

        # Use db module
        if not db.overwrite_game(game_data):
             logger.error("Failed to save game state for the new round.")
             raise RuntimeError("Failed to update game state for next round")

        return end_round_game_state

    except Exception as e:
        logger.exception(f"Error during handle_check_action for game {game_data.get('game_uuid')}")
        raise

# --- Lambda Handler ---
def lambda_handler(event, context):
    logger.info("Received play request.")
    params = None
    try:
        # 1. Parse Input
        params = input.parse_api_gateway_event(event)
        if not params:
            if isinstance(event, dict) and all(k in event for k in ('game_uuid', 'player_uuid', 'action_id')):
                 params = event
                 logger.info("Handling direct invoke event.")
            else:
                 return response.bad_request_response(str(event))

        game_uuid = params.get("game_uuid")
        player_uuid = params.get("player_uuid")
        action_id_param = params.get("action_id")

        # 2. Validate Inputs
        if not input.is_valid_uuid(game_uuid):
            return response.bad_parameter_response("game_uuid", game_uuid, "Invalid game UUID format")
        if not player_uuid:
             return response.bad_parameter_response("player_uuid", player_uuid, "Player UUID missing")
        if not input.is_valid_uuid(player_uuid):
            return response.bad_parameter_response("player_uuid", player_uuid, "Invalid player UUID format")

        if action_id_param is None:
             return response.bad_parameter_response("action_id", action_id_param, "Action ID missing")
        try:
             action_id = int(action_id_param)
             if not (0 <= action_id <= 88): raise ValueError("Action ID out of range")
        except (ValueError, TypeError):
             return response.bad_parameter_response("action_id", action_id_param, "Action ID must be an integer between 0 and 88")

        # 3. Fetch Game Data
        game_data = db.get_game_from_db(game_uuid)
        if not game_data:
            return response.error_response("Game not found", status_code=404)

        # 4. Authorization & Preconditions
        current_status = game_data.get("status")
        if current_status != "Running":
            msg = "Game has not started" if current_status == "Not started" else "Game has finished" if current_status == "Finished" else f"Game status is '{current_status}', cannot play."
            return response.error_response(msg, status_code=400)

        players = game_data.get("players", [])
        cp_nickname = game_data.get("cp_nickname")
        player_nickname = game.get_nickname_by_uuid(players, player_uuid)

        if not player_nickname:
             return response.error_response("Player UUID not found in this game", status_code=403)
        if player_nickname != cp_nickname:
             return response.error_response(f"It is not player '{player_nickname}'s turn (current: '{cp_nickname}')", status_code=403)

        history = game_data.get("history", [])
        if not game.is_legal_action(action_id, history):
            last_action = history[-1].get('action_id') if history else 'None'
            return response.error_response(f"Action {action_id} is not legal now (last action: {last_action})", status_code=400)

        # 5. Perform Action
        game_data["history"].append({"player": player_nickname, "action_id": action_id})

        if action_id == 88: # Check
            response_game_state = handle_check_action(game_data)
        else: # Bid
            next_player = game.find_next_active_player(players, cp_nickname)
            if not next_player:
                 logger.error("Could not find next active player after bid.")
                 raise RuntimeError("Failed to determine next player")
            game_data["cp_nickname"] = next_player.get("nickname")
            # Use db module
            success = db.update_game_play(game_uuid, game_data["cp_nickname"], game_data["history"])
            if not success:
                 logger.error(f"Failed to update game state after bid for {game_uuid}")
                 raise RuntimeError("Failed to update game state in database")
            response_game_state = game_data

        # 6. Censor and Return Response
        # Use game module
        visible_game = game.censor_game_state(response_game_state, player_uuid)
        logger.info(f"Play action {action_id} by {player_nickname} successful for game {game_uuid}.")
        return response.success_response(visible_game)

    except Exception as e:
        game_id_log = params.get('game_uuid') if params else 'unknown'
        logger.exception(f"Error processing play request for game {game_id_log}")
        return response.internal_error_response(e)
