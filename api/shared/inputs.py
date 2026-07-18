import re
import unicodedata
import uuid

def is_valid_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False

def parse_team(value):
    """
    Normalises a team parameter to an int (1-4), or None for an independent player.
    Raises ValueError with a user-facing message for invalid values.
    """
    if value is None:
        return None
    try:
        team = int(value)
    except (ValueError, TypeError):
        raise ValueError("Team must be an integer (1-4) or null")
    if team not in [1, 2, 3, 4]:
        raise ValueError("Team must be 1, 2, 3, 4, or null")
    return team

def parse_nickname(value):
    """
    Normalises a nickname to NFC so a decomposed accent (e.g. "ó" as o + U+0301)
    validates and is stored/looked-up the same as its precomposed form, then
    validates the format: the leading character must be a letter of any script;
    letters, digits and single underscores may follow. No spaces (clients can
    send underscores to represent them) and no leading/trailing/doubled
    underscores. Returns the normalised nickname, or raises ValueError with a
    user-facing message.
    """
    if not isinstance(value, str):
        raise ValueError("Nickname must start with a letter and contain only letters, numbers and single underscores")
    value = unicodedata.normalize("NFC", value)
    if not re.match(r"^[^\W\d_](?:_?[^\W_])*$", value):
        raise ValueError("Nickname must start with a letter and contain only letters, numbers and single underscores")
    return value
