import uuid
import logging

# Shared utilities using the new import style
from shared import response, input, db, game

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info("Received request to join game.")
    params = None
    try:
        # 1. Parse Input
        params = input.parse_api_gateway_event(event)
        if not params:
            return response.bad_request_response(str(event))

        game_uuid = params.get("game_uuid")
        nickname = params.get("nickname")

        # 2. Validate Inputs
        if not input.is_valid_uuid(game_uuid):
            return response.bad_parameter_response("game_uuid", game_uuid, "Invalid game UUID format")
        if not nickname:
             return response.bad_parameter_response("nickname", nickname, "Nickname missing")
        if not input.is_valid_player_nickname(nickname):
             return response.bad_parameter_response("nickname", nickname, "Nickname must start with a letter and contain only letters, numbers, or underscore")

        # 3. Fetch Game Data
        game_data = db.get_game_from_db(game_uuid)
        if not game_data:
            return response.error_response("Game not found", status_code=404)

        # 4. Authorization & Preconditions
        if game_data.get("status") != "Not started":
            return response.error_response("Cannot join game: Game has already started", status_code=403)

        players = game_data.get("players", [])
        if len(players) >= 8:
            return response.error_response("Cannot join game: Game room is full", status_code=403)

        existing_nicknames = [p.get("nickname") for p in players if p.get("nickname")]
        if nickname in existing_nicknames:
             return response.bad_parameter_response("nickname", nickname, "Nickname is already taken in this game")

        # 5. Perform Action: Add Player
        player_uuid = str(uuid.uuid4())
        new_player = { "uuid": player_uuid, "nickname": nickname, "n_cards": 0 }
        players.append(new_player)
        logger.info(f"Prepared new player: {new_player}")

        admin_nickname = game_data.get("admin_nickname")
        needs_admin_update = False
        if not admin_nickname and len(players) == 1:
             admin_nickname = nickname
             needs_admin_update = True
             logger.info(f"Player {nickname} is the first player, setting as admin.")

        # 6. Update Game State in DB
        if needs_admin_update:
             success = db.update_game_players(game_uuid, players, admin_nickname)
        else:
             success = db.update_game_players(game_uuid, players)

        if success:
            logger.info(f"Successfully added player {nickname} to game {game_uuid}.")
            return response.success_response({"player_uuid": player_uuid})
        else:
            logger.error(f"Failed to update game {game_uuid} with new player {nickname}.")
            raise RuntimeError("Failed to update game state in database")

    except Exception as e:
        game_id_log = params.get('game_uuid') if params else 'unknown'
        logger.exception(f"Error joining game {game_id_log}")
        return response.internal_error_response(e)
