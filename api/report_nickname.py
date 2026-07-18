import time
import unicodedata
from shared.response import response_payload, parameter_error_payload, internal_error_payload
from shared.db import reports_table
from shared.game import get_player_by_nickname, get_nickname_by_uuid
from shared.inputs import is_valid_uuid
from shared.decorators import validate_game_request

# Retention period enforced by DynamoDB TTL on the reports table
REPORT_RETENTION_PERIOD_SECONDS = 180 * 24 * 60 * 60  # 180 days
MAX_COMMENT_LENGTH = 500


@validate_game_request()
def lambda_handler(event, context, body, game):
    try:
        players = game.get("players", [])

        reported = body.get("nickname")
        if not reported:
            return parameter_error_payload("nickname", reported, message="Reported nickname missing - please supply it")
        # NFC-normalise before matching: stored nicknames are NFC
        reported = unicodedata.normalize("NFC", str(reported))
        if not get_player_by_nickname(players, reported):
            return parameter_error_payload("nickname", reported, message="Reported nickname not found in this game")

        # Reporting is open to observers, so the reporter identity is optional, but when supplied, it must belong to a player of this game
        reporter_uuid = body.get("player_uuid")
        reporter_nickname = None
        if reporter_uuid is not None:
            reporter_uuid = str(reporter_uuid)
            if not is_valid_uuid(reporter_uuid):
                return parameter_error_payload("player_uuid", reporter_uuid, message="Invalid player UUID")
            reporter_nickname = get_nickname_by_uuid(players, reporter_uuid)
            if not reporter_nickname:
                return parameter_error_payload("player_uuid", reporter_uuid, message="The UUID does not match any player in this game")

        comment = body.get("comment")
        if comment is not None:
            if not isinstance(comment, str):
                return parameter_error_payload("comment", comment, message="Comment must be a string")
            if len(comment) > MAX_COMMENT_LENGTH:
                return parameter_error_payload("comment", f"{len(comment)} characters", message=f"Comment too long (max {MAX_COMMENT_LENGTH} characters)")
            comment = comment or None

        now = int(time.time())
        report = {
            "game_uuid": game["game_uuid"],
            # The key collapses repeat reports (same reporter, same nickname, same game) into a single item
            "report_id": f"{reported}#{reporter_uuid or 'observer'}",
            "reported_nickname": reported,
            "created": now,
            "ttl": now + REPORT_RETENTION_PERIOD_SECONDS
        }
        if reporter_uuid:
            report["reporter_uuid"] = reporter_uuid
            report["reporter_nickname"] = reporter_nickname
        if comment:
            report["comment"] = comment

        reports_table.put_item(Item=report)

        return response_payload(200, {"message": "Report received"})

    except Exception as err:
        return internal_error_payload(err)
