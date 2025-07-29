import time
import decimal
from shared.response import *
from shared.db import table, get_from_dynamodb
from shared.game import unset_human_readiness
from shared.api_gateway import parse_event
from shared.game import update_ai_readiness
from shared.inputs import is_valid_uuid
from shared.logging import logger

def update_in_dynamodb(game_uuid, rules, players):
    # # Unset readiness for all human players after any rule change - for now we only do it if time limit is on
    # players = unset_human_readiness(players)

    table.update_item(
        Key={
            'game_uuid': game_uuid
        },
        UpdateExpression="set #rules = :rules, players = :players, last_modified = :last_modified",
        ExpressionAttributeNames={
            '#rules': 'rules'
        },
        ExpressionAttributeValues={
            ':rules': rules,
            ':players': players,
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
            return error_payload(403, "Cannot change rules after the game has started")

        admin_uuid = str(body.get("admin_uuid"))
        if not is_valid_uuid(admin_uuid):
            return parameter_error_payload("admin_uuid", admin_uuid, message="Invalid admin UUID")

        players = game.get("players")
        game_admin_uuid = [player["uuid"] for player in players if player["nickname"] == game.get("admin_nickname")][0]
        if game_admin_uuid != admin_uuid:
            return parameter_error_payload("admin_uuid", admin_uuid, message="Admin UUID does not match")

        rules = game.get("rules", {})
        
        # Iterate through all query parameters to find and apply rule changes
        for rule, value in body.items():
            # Skip non-rule parameters
            if rule not in rules:
                continue

            # Type conversion for numeric and boolean rules
            if rule in ["time_limit", "deck_size", "common_cards", "jokers", "blanks"]:
                try:
                    value = int(value)
                except (ValueError, TypeError):
                     return parameter_error_payload(rule, value, "Rule must be an integer.")
            elif rule == "standard_order":
                if value == 'True':
                    value = True
                elif value == 'False':
                    value = False
                else:
                    return parameter_error_payload(rule, value, "Standard order must be a boolean string ('True' or 'False').")

            # Validation logic
            if rule == "time_limit":
                if not (0 <= value <= 300):
                    return parameter_error_payload(rule, value, "Time limit must be an integer between 0 and 300")
            elif rule == "deck_size":
                if value not in [24, 32]:
                    return parameter_error_payload(rule, value, "Deck size must be 24 or 32")
            elif rule == "common_cards":
                if not (-1 <= value <= 12):
                    return parameter_error_payload(rule, value, "Common cards must be an integer between 0 and 12")
            elif rule in ["jokers", "blanks"]:
                if not (0 <= value <= 12):
                    return parameter_error_payload(rule, value, "Jokers and blanks must be an integer between 0 and 12")
            
            # Apply the validated rule
            rules[rule] = value
        
        players = update_ai_readiness(players, rules)

        # If time limit is on right now, have every human re-confirm readiness 
        if rules.get("time_limit", 0) > 0:
            players = unset_human_readiness(players)

        logger.info('## NEW RULES')
        logger.info(rules)
        update_in_dynamodb(game_uuid, rules, players)

        return response_payload(200, {"message": "Rules updated"})

    except Exception as err:
        return internal_error_payload(err)
