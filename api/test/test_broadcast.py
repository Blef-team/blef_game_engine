# Unit tests for shared.websocket.broadcast_game_state.
# No network / AWS needed (the management API and the table are stubbed). Run from
# the api/ directory:
#   python test/test_broadcast.py
import os
import sys
import json
import unittest

os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-2")
os.environ.setdefault("AWS_REGION", "eu-west-2")
os.environ.setdefault("watch_game_websocket_api_id", "abc123")
os.environ.setdefault("watch_game_websocket_api_stage", "production")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import shared.websocket as ws  # noqa: E402

GAME_UUID = "11111111-1111-1111-1111-111111111111"
ALICE, BOB = "aaaa-1", "bbbb-2"


class FakeApiGateway:
    exceptions = type("Exceptions", (), {"GoneException": type("GoneException", (Exception,), {})})

    def __init__(self):
        self.sent = []

    def post_to_connection(self, **kwargs):
        self.sent.append((kwargs["ConnectionId"], json.loads(json.loads(kwargs["Data"])["body"])))


class FakeTable:
    def __init__(self, items):
        self.items = items
        self.queries = []

    def query(self, **kwargs):
        self.queries.append(kwargs)
        return {"Items": self.items}


def game(players=None):
    return {
        "game_uuid": GAME_UUID,
        "admin_nickname": "Alice", "public": "false", "room": 1, "status": "Running",
        "round_number": 1, "max_cards": 5, "rules": {}, "history": [], "common_hand": [],
        "cp_nickname": "Alice", "last_modified": 1000.0, "move_deadline": None,
        "players": players or [
            {"uuid": ALICE, "nickname": "Alice", "n_cards": 1},
            {"uuid": BOB, "nickname": "Bob", "n_cards": 1},
        ],
        "hands": [{"nickname": "Alice", "hand": [{"value": 1, "colour": 1}]},
                  {"nickname": "Bob", "hand": [{"value": 2, "colour": 2}]}],
    }


class TestBroadcastGameState(unittest.TestCase):

    def setUp(self):
        self.real_api, self.real_table = ws.apigateway, ws.websocket_table
        ws.apigateway = self.api = FakeApiGateway()

    def tearDown(self):
        ws.apigateway, ws.websocket_table = self.real_api, self.real_table

    def connections(self, *pairs):
        ws.websocket_table = self.table = FakeTable(
            [{"connection_id": c, "player_uuid": p} for c, p in pairs])

    def test_reaches_every_watcher(self):
        self.connections(("c1", ALICE), ("c2", BOB))
        ws.broadcast_game_state(game())
        self.assertEqual({c for c, _ in self.api.sent}, {"c1", "c2"})

    def test_the_mover_is_not_skipped(self):
        self.connections(("c1", ALICE), ("c2", BOB))
        ws.broadcast_game_state(game())
        self.assertEqual(sorted(c for c, _ in self.api.sent), ["c1", "c2"])

    def test_each_recipient_sees_only_their_own_hand(self):
        # The whole state passes through here, so a censoring slip would leak cards.
        self.connections(("c1", ALICE), ("c2", BOB))
        ws.broadcast_game_state(game())
        by_conn = dict(self.api.sent)
        self.assertEqual([h["nickname"] for h in by_conn["c1"]["hands"]], ["Alice"])
        self.assertEqual([h["nickname"] for h in by_conn["c2"]["hands"]], ["Bob"])

    def test_observers_without_a_player_uuid_still_get_it(self):
        self.connections(("c1", None))
        ws.broadcast_game_state(game())
        self.assertEqual(len(self.api.sent), 1)
        self.assertEqual(self.api.sent[0][1]["hands"], [])

    def test_round_snapshots_are_watched_through_the_live_game(self):
        self.connections(("c1", ALICE))
        snapshot = game()
        snapshot["game_uuid"] = f"{GAME_UUID}_4"
        ws.broadcast_game_state(snapshot)
        self.assertEqual(self.table.queries[0]["IndexName"], "game_uuid-index")
        queried = self.table.queries[0]["KeyConditionExpression"].get_expression()["values"][1]
        self.assertEqual(queried, GAME_UUID)

    def test_nobody_connected_sends_nothing(self):
        self.connections()
        ws.broadcast_game_state(game())
        self.assertEqual(self.api.sent, [])

    def test_a_lone_watcher_still_gets_it(self):
        self.connections(("c1", ALICE))
        ws.broadcast_game_state(game())
        self.assertEqual(len(self.api.sent), 1)


if __name__ == "__main__":
    unittest.main()
