import random
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

class AvatarSlots:
    """Fixed cosmetic vocabulary for player avatars.

    Two slots: the mask (which animal) and the material it is carved or cast
    in. The engine is an opaque carrier - it validates that each token is in
    the vocabulary, stores it on the player, and broadcasts it. It never
    interprets or renders the tokens; the rendered appearance is left to
    whatever consumes the API, which maps these tokens to its own art. Only the
    token strings form the contract.

    A few deliberate constraints, recorded to prevent later mistakes:
    - Material is a surface/finish (wood, stone, metal, resin), not a flat
      colour. Keeping appearance out of the engine leaves colour choices to the
      consumer and avoids tokens that could collide with separate colour-coded
      concepts such as team membership.
    - The model shows a mask object, never a human face, so no token implies a
      skin tone.
    - Mask and material tokens are kept distinct from the AI agent names (see
      the invite-aiagent agent mapping) so a player avatar can't be confused
      with an agent.

    Grow the tuples by appending if needed.
    """
    OPTIONS = {
        "mask":     ("tur", "bear", "goat", "stork", "wolf", "raven", "lynx", "zubr"),
        "material": ("wood", "stone", "steel", "gold", "brass", "amber"),
    }
    PARAM_PREFIX = "avatar_"  # wire param names: avatar_mask, avatar_material

def random_avatar():
    """Returns a fully random, valid avatar - one token per slot."""
    return {slot: random.choice(options) for slot, options in AvatarSlots.OPTIONS.items()}

def validate_avatar(body):
    """Builds a player's avatar from flat avatar_<slot> request params.

    Avatars arrive as flat query-string params (avatar_mask, avatar_material):
    the GET endpoints merge query params into `body`, and a flat param can't
    carry a nested object. Provided slots are validated against the vocabulary;
    omitted slots are randomly filled so un-customised players are still
    distinct. Unrelated params are ignored (only the known slot keys are read).

    Returns (avatar_dict, None) on success or (None, error_message) on failure.
    """
    avatar = {}
    for slot, options in AvatarSlots.OPTIONS.items():
        raw = body.get(AvatarSlots.PARAM_PREFIX + slot)
        if raw is None:
            avatar[slot] = random.choice(options)
        elif isinstance(raw, str) and raw in options:
            avatar[slot] = raw
        else:
            return None, f"Invalid value for '{AvatarSlots.PARAM_PREFIX + slot}'"
    return avatar, None
