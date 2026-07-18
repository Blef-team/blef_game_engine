# Maintainer tool: pulls nickname reports from the nickname_reports DynamoDB
# table and prints the ones that arrived since the last run, flagging whether
# each reported nickname is already caught by the profanity filter - the ones
# that pass it are candidates for blocklist additions. The newest report time
# already seen is kept in ~/.blef_reports_state so scheduled runs only surface
# new reports.
#
# Run from any machine with AWS credentials for the account (needs
# dynamodb:Scan on nickname_reports):
#   python deployment/fetch_reports.py          # new reports since last run
#   python deployment/fetch_reports.py --all    # full table, state untouched
import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
from shared.profanity_filter import is_offensive  # noqa: E402

STATE_FILE = Path.home() / ".blef_reports_state"


def load_last_seen():
    try:
        return int(json.loads(STATE_FILE.read_text())["last_created"])
    except (OSError, ValueError, KeyError):
        return 0


def save_last_seen(timestamp):
    STATE_FILE.write_text(json.dumps({"last_created": int(timestamp)}))


def fetch_reports(table):
    items = []
    kwargs = {}
    while True:
        page = table.scan(**kwargs)
        items.extend(page.get("Items", []))
        if "LastEvaluatedKey" not in page:
            return items
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def format_report(report):
    when = datetime.fromtimestamp(int(report["created"]), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    reporter = report.get("reporter_nickname", "observer")
    caught = "caught by filter" if is_offensive(report["reported_nickname"]) else "PASSES filter"
    line = f'[{when}] "{report["reported_nickname"]}" ({caught}) reported by {reporter} in game {report["game_uuid"]}'
    if report.get("comment"):
        line += f'\n    comment: {report["comment"]}'
    return line


def main():
    parser = argparse.ArgumentParser(description="Fetch and triage nickname reports")
    parser.add_argument("--all", action="store_true", help="show the full table and leave the last-seen state untouched")
    args = parser.parse_args()

    table = boto3.resource("dynamodb").Table("nickname_reports")
    reports = fetch_reports(table)

    last_seen = 0 if args.all else load_last_seen()
    new = sorted((r for r in reports if int(r["created"]) > last_seen), key=lambda r: int(r["created"]))
    if not new:
        print("No new reports.")
        return

    print(f"{len(new)} report(s):")
    for report in new:
        print(format_report(report))

    # Distinct rows per (game, nickname) = distinct reporters, since repeat
    # reports by the same reporter overwrite (see report_nickname.py).
    counts = Counter((r["game_uuid"], r["reported_nickname"]) for r in new)
    multi = {k: c for k, c in counts.items() if c > 1}
    if multi:
        print("\nReported by multiple parties:")
        for (game_uuid, nickname), count in sorted(multi.items(), key=lambda kv: -kv[1]):
            print(f'  "{nickname}" in game {game_uuid}: {count} reporters')

    missed = sorted({r["reported_nickname"] for r in new if not is_offensive(r["reported_nickname"])})
    if missed:
        print(f"\nPassing the current profanity filter (blocklist candidates): {', '.join(missed)}")

    if not args.all:
        save_last_seen(max(int(r["created"]) for r in new))


if __name__ == "__main__":
    main()
