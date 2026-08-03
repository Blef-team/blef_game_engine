from shared.response import response_payload, parameter_error_payload, conflict_payload, internal_error_payload
from shared.db import update_players_conditionally
from shared.constants import GameStatus, RuleValues, CommonCardsRules
from shared.game import unset_human_readiness, calculate_actual_max_cards
from shared.decorators import validate_game_request
from shared.logging import logger

@validate_game_request(
    require_admin=True, 
    required_status=GameStatus.NOT_STARTED, 
    status_error_message="Cannot change rules after the game has started"
)
def lambda_handler(event, context, body, game):
    try:
        rules = game.get("rules", {})
        players = game.get("players", [])

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
            elif key == "initial_cards":
                declaration, error = RuleValues.parse_initial_cards_rule(value)
                if error:
                    return parameter_error_payload(key, value, error)
                if declaration is None:
                    rules.pop(key, None)
                else:
                    rules[key] = declaration

        if rules.get("time_limit", RuleValues.TIME_LIMIT_NO_LIMIT) != RuleValues.TIME_LIMIT_NO_LIMIT:
            players = unset_human_readiness(players)

        max_cards = calculate_actual_max_cards(rules, len(players))

        # Checked after the loop so it sees the settled deck size and player
        # count, not the parameter order — but only when this request sets it. A
        # stale rule (a named player left, or the roster grew and max_cards fell)
        # must not block unrelated rule changes; start_game clamps and defaults.
        if "initial_cards" in body:
            error = RuleValues.validate_initial_cards_rule(
                rules.get("initial_cards"), [p["nickname"] for p in players], max_cards)
            if error:
                return parameter_error_payload("initial_cards", body["initial_cards"], error)
            # Uneven openings change the agreed fairness, so re-ask — as change_team does.
            players = unset_human_readiness(players)

        logger.info(f'## NEW RULES: {rules}')
        logger.info(f'## MAX CARDS: {max_cards}')
        if not update_players_conditionally(game["game_uuid"], players, game["last_modified"], rules=rules, max_cards=max_cards):
            return conflict_payload()

        return response_payload(200, {"message": "Rules updated"})

    except Exception as err:
        return internal_error_payload(err)
