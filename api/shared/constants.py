from enum import Enum

class GameStatus:
    NOT_STARTED = "Not started"
    RUNNING = "Running"
    WAITING_FOR_READY = "Waiting for ready"
    FINISHED = "Finished"

class CommonCardsRules(Enum):
    INCREASING = -1
    SLOWLY_INCREASING = -2

    @property
    def rate(self):
        if self == CommonCardsRules.INCREASING:
            return 1/3
        if self == CommonCardsRules.SLOWLY_INCREASING:
            return 1/5
        return 0

    @classmethod
    def special_values(cls):
        return [item.value for item in cls]

class _Range:
    def __init__(self, bottom, top):
        self.BOTTOM = bottom
        self.TOP = top

class RuleValues:
    DECK_SIZES = (24, 32)
    DECK_SIZE_DEFAULT = 24
    JOKERS_RANGE = _Range(0, 12) # We don't envisage players needing more than 12
    JOKERS_DEFAULT = 0
    BLANKS_RANGE = _Range(0, 12) # We don't envisage players needing more than 12
    BLANKS_DEFAULT = 0
    
    TIME_LIMIT_RANGE = _Range(1, 300) # We don't envisage players needing more than 5 minutes. Changing this might need a change in the SQS queue time limit
    TIME_LIMIT_NO_LIMIT = 0
    TIME_LIMIT_DEFAULT = TIME_LIMIT_NO_LIMIT

    MAX_CARDS_FIXED_RANGE = _Range(1, 11)
    MAX_CARDS_NO_PREFERENCE_API = 0
    MAX_CARDS_NO_PREFERENCE_INTERNAL = None
    MAX_CARDS_PREFERENCE_DEFAULT = MAX_CARDS_NO_PREFERENCE_INTERNAL

    COMMON_CARDS_FIXED_RANGE = _Range(0, 12) # We don't envisage players needing more than 12
    COMMON_CARDS_DEFAULT = 0
    
    @classmethod
    def is_valid_time_limit_rule(cls, value):
        """Checks if a value is a valid time limit rule."""
        return (value == cls.TIME_LIMIT_NO_LIMIT) or (cls.TIME_LIMIT_RANGE.BOTTOM <= value <= cls.TIME_LIMIT_RANGE.TOP)

    @classmethod
    def is_valid_common_cards_rule(cls, value):
        """Checks if a value is a valid common cards rule."""
        return (value in CommonCardsRules.special_values()) or (cls.COMMON_CARDS_FIXED_RANGE.BOTTOM <= value <= cls.COMMON_CARDS_FIXED_RANGE.TOP)
    
    @classmethod
    def is_valid_max_cards_rule(cls, value):
        """Checks if a value is a valid max cards preference."""
        return (value == cls.MAX_CARDS_NO_PREFERENCE_API) or (cls.MAX_CARDS_FIXED_RANGE.BOTTOM <= value <= cls.MAX_CARDS_FIXED_RANGE.TOP)

class SpecialNicknames:
    COMMON_HAND = "0"
