import functools
from shared.response import request_error_payload, parameter_error_payload, error_payload
from shared.api_gateway import parse_event
from shared.inputs import is_valid_uuid
from shared.db import get_from_dynamodb
from shared.game import get_nickname_by_uuid

def validate_game_request(require_admin=False, require_player=False, required_status=None, status_error_message=None):
    """
    Decorator to abstract boilerplate validation for game endpoints.
    
    :param require_admin: If True, validates 'admin_uuid' against the game's admin player.
    :param require_player: If True, validates 'player_uuid' and ensures they are in the game.
    :param required_status: A string or list of strings from GameStatus. Ensures game matches this state.
    :param status_error_message: Optional custom message if the status check fails.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(event, context):
            # Parse and validate base request
            body = parse_event(event)
            if not body:
                return request_error_payload(event)

            # Validate Game UUID and fetch game
            game_uuid = str(body.get("game_uuid"))
            if not is_valid_uuid(game_uuid):
                return parameter_error_payload("game_uuid", game_uuid, message="Invalid game UUID")

            game = get_from_dynamodb(game_uuid)
            if not game:
                return parameter_error_payload("game_uuid", game_uuid, message="Game does not exist")

            # Validate Game Status
            if required_status:
                current_status = game.get("status")
                is_valid_status = (
                    current_status in required_status if isinstance(required_status, list) 
                    else current_status == required_status
                )
                if not is_valid_status:
                    msg = status_error_message or f"Action forbidden. Current game status is: {current_status}"
                    return error_payload(403, msg)

            # Validate Admin Authenticity
            if require_admin:
                admin_uuid = body.get("admin_uuid")
                if not admin_uuid:
                    return parameter_error_payload("admin_uuid", admin_uuid, message="Admin UUID missing - please supply it")
                
                admin_uuid = str(admin_uuid)
                if not is_valid_uuid(admin_uuid):
                    return parameter_error_payload("admin_uuid", admin_uuid, message="Invalid admin UUID")

                players = game.get("players", [])
                admin_players = [p for p in players if p.get("nickname") == game.get("admin_nickname")]
                
                if not admin_players or admin_players[0]["uuid"] != admin_uuid:
                    return parameter_error_payload("admin_uuid", admin_uuid, message="Admin UUID does not match")

            # Validate Standard Player Authenticity
            if require_player:
                player_uuid = body.get("player_uuid")
                if not player_uuid:
                    return parameter_error_payload("player_uuid", player_uuid, message="Player UUID missing - please supply it")
                
                player_uuid = str(player_uuid)
                if not is_valid_uuid(player_uuid):
                    return parameter_error_payload("player_uuid", player_uuid, message="Invalid player UUID")

                player_nickname = get_nickname_by_uuid(game.get("players", []), player_uuid)
                if not player_nickname:
                    return parameter_error_payload("player_uuid", player_uuid, message="The UUID does not match any active player")
                
                # Attach the validated nickname to the body so the handler doesn't have to look it up again
                body["player_nickname"] = player_nickname

            # Execute the actual Lambda handler
            return func(event, context, body, game)
            
        return wrapper
    return decorator
