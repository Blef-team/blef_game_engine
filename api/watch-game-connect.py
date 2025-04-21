import logging

# Shared utilities using the new import style
from shared import response, input, db, game, websocket

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info("WebSocket connect request received.")
    connection_id = None
    try:
        # 1. Get Connection ID (Essential) - Use input module
        connection_id = input.get_connection_id(event)
        logger.info(f"Registering connection ID: {connection_id}")

        # 2. Extract Optional Parameters
        query_params = event.get('queryStringParameters') or {}
        game_uuid = query_params.get('game_uuid')
        player_uuid = query_params.get('player_uuid')
        reactions_enabled_str = query_params.get('reactions_enabled', 'false')
        logger.info(f"Connection Params - Game: {game_uuid}, Player: {player_uuid}, Reactions: {reactions_enabled_str}")

        # 3. Validate Parameters - Use input module
        if game_uuid and not input.is_valid_uuid(game_uuid):
             return response.format_response(400, {"error": "Invalid game_uuid format"})
        if player_uuid and not input.is_valid_uuid(player_uuid):
             return response.format_response(400, {"error": "Invalid player_uuid format"})

        # 4. Validate Game/Player Existence (Optional)
        if game_uuid:
             # Use db module
             game_data = db.get_game_from_db(game_uuid)
             if not game_data:
                 return response.format_response(404, {"error": "Game not found"})
             if player_uuid:
                  # Use game module
                  nickname = game.get_nickname_by_uuid(game_data.get("players", []), player_uuid)
                  if not nickname:
                      return response.format_response(403, {"error": "Player not found in specified game"})

        # 5. Save Connection Info - Use websocket module
        reactions_enabled = reactions_enabled_str.lower() == 'true'
        success = websocket.save_connection(
            connection_id, game_uuid, player_uuid, reactions_enabled
        )

        # 6. Return Success Response - Use response module
        if success:
            logger.info(f"Connection {connection_id} registered successfully.")
            return response.format_response(200, {"message": "Connected"})
        else:
            logger.error(f"Failed to save connection {connection_id} to database.")
            return response.format_response(500, {"error": "Failed to register connection"})

    except ValueError as ve: # From get_connection_id
         logger.error(f"Value error during connect: {ve}")
         return response.format_response(400, {"error": str(ve)})
    except Exception as e:
        logger.exception(f"Error handling WebSocket connect for connection {connection_id}")
        return response.format_response(500, {"error": "Internal server error during connection"})
