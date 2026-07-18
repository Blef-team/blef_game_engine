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
