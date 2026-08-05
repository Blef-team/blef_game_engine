# Unit tests for play's conditional write and its direct websocket push.
# No network / AWS needed (the DynamoDB table is stubbed). Run from the api/ directory:
#   python test/test_play.py
import os
import sys
import decimal
import unittest

os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-2")
# play broadcasts, so it pulls in shared.websocket's endpoint construction
os.environ.setdefault("AWS_REGION", "eu-west-2")
os.environ.setdefault("watch_game_websocket_api_id", "abc123")
os.environ.setdefault("watch_game_websocket_api_stage", "production")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import play  # noqa: E402
from botocore.exceptions import ClientError  # noqa: E402


class FakeTable:
    def __init__(self, error_code=None):
        self.error_code = error_code
        self.calls = []

    def update_item(self, **kwargs):
        self.calls.append(kwargs)
        if self.error_code:
            raise ClientError({'Error': {'Code': self.error_code}}, 'UpdateItem')


class TestUpdateInDynamodb(unittest.TestCase):

    def setUp(self):
        self.real_table = play.table
        self.args = ("uuid-1", "Bob", [{"player": "Alice", "action_id": 5}],
                     decimal.Decimal("2000"), decimal.Decimal("1000"), decimal.Decimal("3000"))

    def tearDown(self):
        play.table = self.real_table

    def update(self):
        return play.update_in_dynamodb(*self.args)

    def test_success_returns_true_and_guards_on_last_modified(self):
        play.table = fake = FakeTable()
        self.assertTrue(self.update())
        call = fake.calls[0]
        self.assertEqual(call['ConditionExpression'], "last_modified = :lm")
        self.assertEqual(call['ExpressionAttributeValues'][':lm'], decimal.Decimal("1000"))
        # The caller puts this same value on the game dict before broadcasting, so the
        # direct push and the stream's copy agree on when the write happened.
        self.assertEqual(call['ExpressionAttributeValues'][':t'], decimal.Decimal("3000"))

    def test_lost_condition_check_returns_false(self):
        play.table = FakeTable(error_code='ConditionalCheckFailedException')
        self.assertFalse(self.update())

    def test_transaction_conflict_returns_false(self):
        # A timeout ending the round runs transact_write_items; DynamoDB rejects
        # singleton writes to the same item while that is in flight. The play
        # lost the race, so it must not surface as a 500.
        play.table = FakeTable(error_code='TransactionConflictException')
        self.assertFalse(self.update())

    def test_other_client_errors_propagate(self):
        play.table = FakeTable(error_code='ProvisionedThroughputExceededException')
        with self.assertRaises(ClientError):
            self.update()



HUMAN_A, HUMAN_B, AI = "human-a", "human-b", "ai-1"


def roster(*players):
    return {"players": list(players)}


def human(uuid, nickname):
    return {"uuid": uuid, "nickname": nickname}


def ai(uuid, nickname):
    return {"uuid": uuid, "nickname": nickname, "ai_agent": "conservative"}


class TestPushToOtherPlayers(unittest.TestCase):
    """Who gets a move ahead of the DynamoDB stream, and who waits for it."""

    def setUp(self):
        self.real_broadcast = play.broadcast_game_state
        self.pushed = []
        play.broadcast_game_state = lambda game, exclude_player_uuid=None: self.pushed.append(exclude_player_uuid)

    def tearDown(self):
        play.broadcast_game_state = self.real_broadcast

    def test_human_move_with_another_human_watching_is_pushed(self):
        play.push_to_other_players(roster(human(HUMAN_A, "A"), human(HUMAN_B, "B")), HUMAN_A)
        self.assertEqual(self.pushed, [HUMAN_A])

    def test_ai_move_is_left_to_the_stream(self):
        # AI agents invoke blef-play directly, so without this check their moves would
        # be pushed too - most of the traffic, for a move the queue already paced.
        play.push_to_other_players(roster(human(HUMAN_A, "A"), human(HUMAN_B, "B"), ai(AI, "Dazhbog_(AI)")), AI)
        self.assertEqual(self.pushed, [])

    def test_single_human_game_is_left_to_the_stream(self):
        play.push_to_other_players(roster(human(HUMAN_A, "A"), ai(AI, "Dazhbog_(AI)")), HUMAN_A)
        self.assertEqual(self.pushed, [])

    def test_unknown_mover_pushes_nothing(self):
        play.push_to_other_players(roster(human(HUMAN_A, "A"), human(HUMAN_B, "B")), "not-in-this-game")
        self.assertEqual(self.pushed, [])


if __name__ == "__main__":
    unittest.main()
