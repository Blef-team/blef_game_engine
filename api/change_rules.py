import time
import decimal
from shared.response import *
from shared.db import table, get_from_dynamodb
from shared.constants import GameStatus, RuleValues, CommonCardsRules
from shared.game import unset_human_readiness, calculate_actual_max_cards
from shared.api_gateway import parse_event
from shared.inputs import is_valid_uuid
from shared.logging import logger

def update_in_dynamodb(game_uuid, rules, players, max_cards=None):
    """
    Updates the game rules, player readiness, and max cards in DynamoDB.
    """
    update_expressions = ["#rules = :rules", "players = :players", "last_modified = :last_modified"]
    expression_attribute_names = {'#rules': 'rules'}
    expression_attribute_values = {
        ':rules': rules,
        ':players': players,
        ':last_modified': decimal.Decimal(str(time.time()))
    }

    if max_cards is not None:
        update_expressions.append("max_cards = :max_cards")
        expression_attribute_values[':max_cards'] = max_cards

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

        if game.get("status") != GameStatus.NOT_STARTED:
            return error_payload(403, "Cannot change rules after the game has started")

        admin_uuid = str(body.get("admin_uuid"))
        if not is_valid_uuid(admin_uuid):
            return parameter_error_payload("admin_uuid", admin_uuid, message="Invalid admin UUID")

        players = game.get("players")
        game_admin_uuid = [player["uuid"] for player in players if player["nickname"] == game.get("admin_nickname")][0]
        if game_admin_uuid != admin_uuid:
            return parameter_error_payload("admin_uuid", admin_uuid, message="Admin UUID does not match")

        rules = game.get("rules", {})

        for key, value in body.items():
            if key in ["time_limit", "deck_size", "common_cards", "jokers", "blanks", "max_cards"]:
                try:
                    value = int(value)
                except (ValueError, TypeError):
                     return parameter_error_payload(key, value, "Every rule must be an integer.")

            if key == "time_limit":
                if not RuleValues.is_valid_time_limit_rule(value):
                    return parameter_error_payload(key, value, 
                        f"Time limit must be {RuleValues.TIME_LIMIT_NO_LIMIT} (for no limit) or an integer between "
                        f"{RuleValues.TIME_LIMIT_RANGE.BOTTOM} and {RuleValues.TIME_LIMIT_RANGE.TOP}")
                rules[key] = value
            elif key == "deck_size":
                if value not in RuleValues.DECK_SIZES:
                    return parameter_error_payload(key, value, f"Deck size must be one of {RuleValues.DECK_SIZES}")
                rules[key] = value
            elif key == "common_cards":
                if not RuleValues.is_valid_common_cards_rule(value):
                    return parameter_error_payload(key, value,
                        f"Common cards must be between {RuleValues.COMMON_CARDS_FIXED_RANGE.BOTTOM} and "
                        f"{RuleValues.COMMON_CARDS_FIXED_RANGE.TOP}, or one of the special values: "
                        f"{CommonCardsRules.special_values()}")
                rules[key] = value
            elif key == "jokers":
                if not (RuleValues.JOKERS_RANGE.BOTTOM <= value <= RuleValues.JOKERS_RANGE.TOP):
                    return parameter_error_payload(key, value, f"Jokers must be an integer between {RuleValues.JOKERS_RANGE.BOTTOM} and {RuleValues.JOKERS_RANGE.TOP}")
                rules[key] = value
            elif key == "blanks":
                if not (RuleValues.BLANKS_RANGE.BOTTOM <= value <= RuleValues.BLANKS_RANGE.TOP):
                    return parameter_error_payload(key, value, f"Blanks must be an integer between {RuleValues.BLANKS_RANGE.BOTTOM} and {RuleValues.BLANKS_RANGE.TOP}")
                rules[key] = value
            elif key == "max_cards":
                if not RuleValues.is_valid_max_cards_rule(value):
                    return parameter_error_payload(key, value,
                        f"Max cards must be {RuleValues.MAX_CARDS_NO_PREFERENCE_API} (for no preference) or an integer between "
                        f"{RuleValues.MAX_CARDS_FIXED_RANGE.BOTTOM} and {RuleValues.MAX_CARDS_FIXED_RANGE.TOP}")
                rules["max_cards_preference"] = value if value != RuleValues.MAX_CARDS_NO_PREFERENCE_API else RuleValues.MAX_CARDS_NO_PREFERENCE_INTERNAL

        if rules.get("time_limit", RuleValues.TIME_LIMIT_NO_LIMIT) != RuleValues.TIME_LIMIT_NO_LIMIT:
            players = unset_human_readiness(players)

        max_cards = calculate_actual_max_cards(rules, len(players))

        logger.info(f'## NEW RULES: {rules}')
        logger.info(f'## MAX CARDS: {max_cards}')
        update_in_dynamodb(game_uuid, rules, players, max_cards)

        return response_payload(200, {"message": "Rules updated"})

    except Exception as err:
        return internal_error_payload(err)
