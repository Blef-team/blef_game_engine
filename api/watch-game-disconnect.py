import boto3
from boto3.dynamodb.conditions import Key, Attr
import json
import decimal
import uuid
from shared.response import * 
from shared.api_gateway import parse_event, get_connection_id
from shared.db import websocket_table



def delete_connection_object(connection_id):
    websocket_table.delete_item(
            Key={
                'connection_id': connection_id
            })
    return True


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
