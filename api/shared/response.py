import json
import logging
from shared.db import DecimalEncoder # Import from renamed db module

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def format_response(status_code, body, is_error=False):
    """ Creates a standard API Gateway response payload. """
    if is_error and isinstance(body, str):
        body_payload = {"error": body}
    else:
        body_payload = body

    try:
        body_json = json.dumps(body_payload, cls=DecimalEncoder)
    except TypeError as e:
         logger.error(f"TypeError during JSON encoding: {e}. Payload: {body_payload}")
         # Fallback for unhandled types? Or raise?
         body_json = json.dumps({"error": "Internal serialization error"})
         status_code = 500

    return {
        'statusCode': status_code,
        'body': body_json,
        'headers': {
            # Consider making CORS headers more specific if possible
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,x-api-key,X-Amz-Security-Token',
            'Access-Control-Allow-Origin': '*', # Restrict in production
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET', # Adjust per API method
            'Access-Control-Allow-Credentials': True,
            'Content-Type': 'application/json'
        },
    }

def success_response(body, status_code=200):
    """ Formats a successful API Gateway response. """
    return format_response(status_code, body, is_error=False)

def error_response(message, status_code=400):
    """ Formats a client error API Gateway response (4xx). """
    logger.warning(f"Returning error response ({status_code}): {message}")
    return format_response(status_code, message, is_error=True)

def internal_error_response(exception, message="Internal Lambda function error"):
    """ Formats a 500 internal server error response. Logs the exception. """
    # Log the full exception details server-side
    logger.exception(f"{message}: {exception}")
    # Return a generic error message to the client
    return format_response(500, {"error": "An internal server error occurred."}, is_error=True)

def bad_request_response(request_data, message="Bad request payload"):
    """ Formats a 400 Bad Request response, logging the problematic data. """
    error_message = f"{message}: '{request_data}'"
    logger.warning(f"Bad request: {error_message}") # Log the request data
    return error_response(error_message, 400)

def bad_parameter_response(param_key, param_value, message="Bad input value"):
    """ Formats a 400 Bad Request response for a specific invalid parameter. """
    error_message = f"{message} in '{param_key}': {param_value}"
    logger.warning(f"Bad parameter: {error_message}") # Log the specific param issue
    return error_response(error_message, 400)