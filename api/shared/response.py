"""
Handles formatting API Gateway responses and encoding Decimal types for JSON.
"""
import json
import decimal

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            if obj.as_tuple().exponent == 0:
                return int(obj)
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def _get_cors_headers():
    """ Returns default CORS headers. """
    return {
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,x-api-key,X-Amz-Security-Token',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
        'Access-Control-Allow-Credentials': True,
        'Content-Type': 'application/json'
    }

def response_payload(status_code, body):
    """ Creates a standard API Gateway success response payload. """
    return {
        'statusCode': status_code,
        'body': json.dumps(body, cls=DecimalEncoder),
        'headers': _get_cors_headers(),
    }

def error_payload(status_code, error_message):
    """ Creates a standard API Gateway error response payload. """
    return response_payload(status_code, {"error": error_message})

def internal_error_payload(err, message=None):
    """ Creates a 500 Internal Server Error response payload. """
    body = f"Internal Lambda function error: {err}"
    if message:
        body = f"{body}\n{message}"
    return error_payload(500, body)

def request_error_payload(request, message=None):
    """ Creates a 400 Bad Request response payload for invalid request structure. """
    body = f"Bad request payload: '{request}'"
    if message:
        body = f"{body}\n{message}"
    return error_payload(400, body)

def parameter_error_payload(param_key, param_value, message=None):
    """ Creates a 400 Bad Request response payload for invalid parameter values. """
    body = f"Bad input value in '{param_key}': {param_value}"
    if message:
        body = f"{body}\n{message}"
    return error_payload(400, body)
