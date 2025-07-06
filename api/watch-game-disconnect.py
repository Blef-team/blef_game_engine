import boto3
from boto3.dynamodb.conditions import Key, Attr
import json
import decimal
import uuid
from shared.response import * 
from shared.api_gateway import parse_event


dynamodb = boto3.resource('dynamodb')
websocket_table = dynamodb.Table("watch_game_websocket_manager")


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
