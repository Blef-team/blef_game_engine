import time
import decimal
from shared.response import response_payload, internal_error_payload
from shared.db import table
from shared.constants import GameStatus
from shared.game import calculate_actual_max_cards
from shared.decorators import validate_game_request

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

@validate_game_request(
    require_admin=True, 
    required_status=GameStatus.NOT_STARTED, 
    status_error_message="Cannot remove AIs after the game has started"
)
def lambda_handler(event, context, body, game):
    try:
        players = game.get("players", [])
        human_players = [p for p in players if not p.get("ai_agent")]

        if len(human_players) == len(players):
            return response_payload(200, {"message": "No AI players to remove."})
        
        max_cards = calculate_actual_max_cards(game.get("rules", {}), len(human_players))

        update_in_dynamodb(game["game_uuid"], human_players, max_cards)

        return response_payload(200, {"message": "All AI players have been removed."})

    except Exception as err:
        return internal_error_payload(err)
