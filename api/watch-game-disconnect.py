import logging

# Shared utilities using the new import style
from shared import response, input, websocket

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info("WebSocket disconnect request received.")
    connection_id = None
    try:
        # 1. Get Connection ID - Use input module
        connection_id = input.get_connection_id(event)
        logger.info(f"Unregistering connection ID: {connection_id}")

        # 2. Delete Connection Info from DB - Use websocket module
        success = websocket.delete_connection(connection_id)

        # 3. Return Success Response - Use response module
        logger.info(f"Connection {connection_id} processing finished (DB delete success: {success}).")
        return response.format_response(200, {"message": "Disconnected"})

    except ValueError as ve: # From get_connection_id
         logger.error(f"Value error during disconnect: {ve}")
         return response.format_response(400, {"error": str(ve)})
    except Exception as e:
        logger.exception(f"Error handling WebSocket disconnect for connection {connection_id}")
        return response.format_response(200, {"message": "Disconnect processed with error"}) # Still return 200
