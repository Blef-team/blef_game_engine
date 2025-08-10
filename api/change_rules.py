import time
import decimal
from shared.response import *
from shared.db import table, get_from_dynamodb
from shared.game import unset_human_readiness
from shared.api_gateway import parse_event
from shared.game import update_ai_readiness
from shared.inputs import is_valid_uuid
from shared.logging import logger

def update_in_dynamodb(game_uuid, rules, players, max_cards_update=None):
    update_expressions = ["#rules = :rules", "players = :players", "last_modified = :last_modified"]
    expression_attribute_names = {'#rules': 'rules'}
    expression_attribute_values = {
        ':rules': rules,
        ':players': players,
        ':last_modified': decimal.Decimal(str(time.time()))
    }

    if max_cards_update is not None:
        update_expressions.append("max_cards = :max_cards")
        expression_attribute_values[':max_cards'] = max_cards_update

    table.update_item(
        Key={'game_uuid': game_uuid},
        UpdateExpression="set " + ", ".join(update_expressions),
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values,
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
        max_cards_update = None

        # Iterate through all query parameters to find and apply changes
        for key, value in body.items():
            # Type conversion - right now all rules are integers
            if key in ["time_limit", "deck_size", "common_cards", "jokers", "blanks", "max_cards"]:
                try:
                    value = int(value)
                except (ValueError, TypeError):
                     return parameter_error_payload(key, value, "Rule must be an integer.")

            if key == "time_limit":
                if not (0 <= value <= 300):
                    return parameter_error_payload(key, value, "Time limit must be an integer between 0 and 300")
                rules[key] = value
            elif key == "deck_size":
                if value not in [24, 32]:
                    return parameter_error_payload(key, value, "Deck size must be 24 or 32")
                rules[key] = value
            elif key == "common_cards":
                if not (-2 <= value <= 12):
                    return parameter_error_payload(key, value, "Common cards must be an integer between 0 and 12")
                rules[key] = value
            elif key in ["jokers", "blanks"]:
                if not (0 <= value <= 12):
                    return parameter_error_payload(key, value, "Jokers and blanks must be an integer between 0 and 12")
                rules[key] = value
            elif key == "max_cards":
                if not (0 <= value <= 11):
                    return parameter_error_payload(key, value, "Max cards must be 0 (for auto) or an integer between 1 and 11")
                max_cards_update = value

        players = update_ai_readiness(players, rules)

        if rules.get("time_limit", 0) > 0:
            players = unset_human_readiness(players)

        logger.info(f'## NEW RULES: {rules}')
        logger.info(f'## MAX CARDS UPDATE: {max_cards_update}')
        update_in_dynamodb(game_uuid, rules, players, max_cards_update)

        return response_payload(200, {"message": "Rules updated"})

    except Exception as err:
        return internal_error_payload(err)
