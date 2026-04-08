import time
import decimal
from shared.response import response_payload, internal_error_payload
from shared.db import table
from shared.constants import GameStatus
from shared.decorators import validate_game_request


def update_in_dynamodb(game_uuid, public):
    table.update_item(
        Key={
            'game_uuid': game_uuid
        },
        UpdateExpression="set last_modified = :last_modified, #game_public = :public",
        ExpressionAttributeValues={
            ':last_modified': decimal.Decimal(str(time.time())),
            ':public': public
        },
        ExpressionAttributeNames={
            '#game_public': "public"
        },
        ReturnValues="NONE"
    )
    return True

@validate_game_request(
    require_admin=True, 
    required_status=GameStatus.NOT_STARTED, 
    status_error_message="Cannot make the change - game already started"
)
def lambda_handler(event, context, body, game):
    try:
        if game.get("public") == "true":
            return response_payload(200, {"message": "Request redundant - game already public"})

        update_in_dynamodb(game["game_uuid"], "true")
        return response_payload(200, {"message": "Game made public"})

    except Exception as err:
        return internal_error_payload(err)
