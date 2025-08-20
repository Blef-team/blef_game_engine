import time
import decimal
from shared.response import *
from shared.db import table, get_from_dynamodb
from shared.api_gateway import parse_event
from shared.game import calculate_actual_max_cards
from shared.inputs import is_valid_uuid

def update_in_dynamodb(game_uuid, players, max_cards):
    table.update_item(
        Key={
            'game_uuid': game_uuid
        },
        UpdateExpression="set players = :players, max_cards = :mc, last_modified = :last_modified",
        ExpressionAttributeValues={
            ':players': players,
            ':mc': max_cards,
            ':last_modified': decimal.Decimal(str(time.time()))
        },
        ReturnValues="NONE"
    )
    return True

def lambda_handler(event, context):
    try:
        body = parse_event(event)
        if not body:
            return request_error_payload(event)

        game_uuid = str(body.get("game_uuid"))
        if not is_valid_uuid(game_uuid):
            return parameter_error_payload("game_uuid", game_uuid, message="Invalid game UUID")

        game = get_from_dynamodb(game_uuid)
        if not game:
            return parameter_error_payload("game_uuid", game_uuid, message="Game does not exist")

        if game.get("status") != "Not started":
            return error_payload(403, "Cannot remove AIs after the game has started")

        admin_uuid = str(body.get("admin_uuid"))
        if not is_valid_uuid(admin_uuid):
            return parameter_error_payload("admin_uuid", admin_uuid, message="Invalid admin UUID")

        players = game.get("players")            
        game_admin_uuid = [player["uuid"] for player in players if player["nickname"] == game.get("admin_nickname")][0]
        if game_admin_uuid != admin_uuid:
            return parameter_error_payload("admin_uuid", admin_uuid, message="Admin UUID does not match")

        human_players = [p for p in players if not p.get("ai_agent")]

        if len(human_players) == len(players):
            return response_payload(200, {"message": "No AI players to remove."})
        
        max_cards = calculate_actual_max_cards(game.get("rules", {}), len(human_players))

        update_in_dynamodb(game_uuid, human_players, max_cards)

        return response_payload(200, {"message": "All AI players have been removed."})

    except Exception as err:
        return internal_error_payload(err)
