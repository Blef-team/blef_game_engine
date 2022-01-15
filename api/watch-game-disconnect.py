import boto3
from boto3.dynamodb.conditions import Key, Attr
import json
import decimal
import uuid


dynamodb = boto3.resource('dynamodb')
websocket_table = dynamodb.Table("watch_game_websocket_manager")

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            if obj.as_tuple().exponent == 0:
                return int(obj)
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def response_payload(status_code, body):
    return {
            'statusCode': status_code,
            'body': json.dumps(body, cls=DecimalEncoder),
            'headers': {
                'Access-Control-Allow-Headers':'Content-Type,X-Amz-Date,Authorization,X-Api-Key,x-api-key,X-Amz-Security-Token',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
                'Access-Control-Allow-Credentials': True,
                'Content-Type': 'application/json'
            },
        }


def error_payload(status_code, body):
    return response_payload(status_code, {"error": body})


def internal_error_payload(err, message=None):
    body = "Internal Lambda function error: {}".format(err)
    if message:
        body = "{}\n{}".format(body, message)
    return error_payload(500, body)


def request_error_payload(request, message=None):
    body = "Bad request payload: '{}'".format(request)
    if message:
        body = "{}\n{}".format(body, message)
    return error_payload(400, body)


def parameter_error_payload(param_key, param_value, message=None):
    body = "Bad input value in '{}': {}".format(param_key, param_value)
    if message:
        body = "{}\n{}".format(body, message)
    return error_payload(400, body)


def parse_event(event):
    # Basic input validation
    if not isinstance(event, dict):
        return False

    # Handle both direct triggers and API Gateway
    body = event.get("body", event)
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError:
            return None
    path_params = event.get("pathParameters", {})
    query_params = event.get("queryStringParameters", {})
    body.update(path_params)
    body.update(query_params)
    return body


def is_valid_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def delete_connection_object(connection_id):
    websocket_table.delete_item(
            Key={
                'connection_id': connection_id
            })
    return True


def get_connection_id(event, context, body):
    if context and hasattr(context, 'get') and context.get("connectionId"):
        return context.get("connectionId")
    if "connectionId" in event.get("requestContext", {}):
        return event["requestContext"]["connectionId"]
    if "connectionId" in event:
        return event["connectionId"]
    if "connectionId" in body:
        return body["connectionId"]
    raise ValueError("Request context is invalid!")


def lambda_handler(event, context):
    try:
        body = parse_event(event)
        if not body:
            return request_error_payload(event)

        connection_id = get_connection_id(event, context, body)

        if delete_connection_object(connection_id):
            return response_payload(200, {"message": "Disconnected"})

        raise(Exception("Something went wrong - ended up with no response"))

    except Exception as err:
        return internal_error_payload(err)
