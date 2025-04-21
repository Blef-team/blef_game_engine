import logging

# Shared utilities using the new import style
from shared import response, db

logger = logging.getLogger()
logger.setLevel(logging.INFO)

MAX_LISTING_AGE_SECONDS = 1800 # 30 minutes

def lambda_handler(event, context):
    logger.info("Received request to list public games.")
    try:
        # 1. Fetch recently active public games from DB
        games_data = db.get_recently_active_public_games(MAX_LISTING_AGE_SECONDS)
        logger.info(f"Found {len(games_data)} recently active public games.")

        # 2. Format the response payload
        games_info = []
        for game_item in games_data:
             players_list = game_item.get("players", [])
             player_nicknames = [p.get("nickname") for p in players_list if p.get("nickname")]
             games_info.append({
                 "game_uuid": game_item.get("game_uuid"),
                 "room": game_item.get("room"),
                 "players": player_nicknames,
                 "last_modified": game_item.get("last_modified")
             })

        # 3. Return the formatted list
        return response.success_response(games_info)

    except Exception as e:
        logger.exception("Error listing public games.")
        return response.internal_error_response(e, "Error retrieving public game list")
