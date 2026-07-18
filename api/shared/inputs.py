import re
import unicodedata
import uuid

def is_valid_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False

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
