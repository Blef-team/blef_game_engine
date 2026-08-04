# Unit tests for the readiness path's conditional writes.
# No network / AWS needed (the DynamoDB table is stubbed). Run from the api/ directory:
#   python test/test_readiness.py
import os
import sys
import copy
import decimal
import unittest

os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-2")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import set_readiness  # noqa: E402
import shared.game as game_module  # noqa: E402
import shared.decorators as decorators  # noqa: E402
from shared.constants import GameStatus  # noqa: E402
from botocore.exceptions import ClientError  # noqa: E402

GAME_UUID = "11111111-1111-1111-1111-111111111111"
ADMIN_UUID = "22222222-2222-2222-2222-222222222222"
BOB_UUID = "33333333-3333-3333-3333-333333333333"


def player(uuid, nickname, ready=False, team=None):
    return {"uuid": uuid, "nickname": nickname, "n_cards": 0, "ready": ready, "team": team}


def lobby(players=None, **overrides):
    game = {
        "game_uuid": GAME_UUID,
        "status": GameStatus.NOT_STARTED,
        "admin_nickname": "Admin",
        "max_cards": 5,
        "rules": {},
        "history": [],
        "players": players if players is not None else [
            player(ADMIN_UUID, "Admin"), player(BOB_UUID, "Bob")],
        "last_modified": decimal.Decimal("1000"),
    }
    game.update(overrides)
    return game


class FakeTable:
    """Records writes and fails the first `fail_times` of them with `error_code`."""

    def __init__(self, error_code=None, fail_times=0):
        self.error_code = error_code
        self.fail_times = fail_times
        self.calls = []

    def update_item(self, **kwargs):
        self.calls.append(kwargs)
        if self.error_code and len(self.calls) <= self.fail_times:
            raise ClientError({'Error': {'Code': self.error_code}}, 'UpdateItem')
        return {'Attributes': lobby()}


class TestUpdatePlayerReadiness(unittest.TestCase):

    def setUp(self):
        self.real_table = set_readiness.table

    def tearDown(self):
        set_readiness.table = self.real_table

    def write(self, index=1):
        return set_readiness.update_player_readiness(GAME_UUID, index, BOB_UUID, True)

    def test_write_is_guarded_on_the_uuid_in_that_slot(self):
        set_readiness.table = fake = FakeTable()
        self.assertIsNotNone(self.write())

        call = fake.calls[0]
        self.assertEqual(call['ConditionExpression'], "players[1].#uuid = :player_uuid")
        self.assertEqual(call['ExpressionAttributeValues'][':player_uuid'], BOB_UUID)
        # "uuid" is a DynamoDB reserved word, so the path has to go through a placeholder.
        self.assertEqual(call['ExpressionAttributeNames']['#uuid'], "uuid")
        self.assertIn("players[1].ready = :ready", call['UpdateExpression'])

    def test_lost_race_returns_none(self):
        set_readiness.table = FakeTable(error_code='ConditionalCheckFailedException', fail_times=1)
        self.assertIsNone(self.write())

    def test_transaction_conflict_returns_none(self):
        set_readiness.table = FakeTable(error_code='TransactionConflictException', fail_times=1)
        self.assertIsNone(self.write())

    def test_other_client_errors_propagate(self):
        set_readiness.table = FakeTable(error_code='ProvisionedThroughputExceededException', fail_times=1)
        with self.assertRaises(ClientError):
            self.write()


class TestReadinessHandler(unittest.TestCase):
    """A write the roster shifted under must be refused, not landed on whoever took the index."""

    def setUp(self):
        self.real_table = set_readiness.table
        self.real_get = decorators.get_from_dynamodb
        self.real_start = set_readiness.start_game
        set_readiness.start_game = lambda game: True

    def tearDown(self):
        set_readiness.table = self.real_table
        decorators.get_from_dynamodb = self.real_get
        set_readiness.start_game = self.real_start

    def call(self, game):
        decorators.get_from_dynamodb = lambda _uuid: copy.deepcopy(game)
        return set_readiness.lambda_handler(
            {"pathParameters": {"game_uuid": GAME_UUID},
             "queryStringParameters": {"player_uuid": BOB_UUID, "ready": "True"}}, None)

    def test_happy_path_writes_once(self):
        set_readiness.table = fake = FakeTable()
        resp = self.call(lobby())
        self.assertEqual(resp["statusCode"], 200)
        self.assertEqual(len(fake.calls), 1)

    def test_lost_race_reports_conflict(self):
        # The roster shifted, so the write was refused rather than landing on the
        # player who took the index. Repeating the call is the client's job.
        set_readiness.table = fake = FakeTable(error_code='ConditionalCheckFailedException', fail_times=1)
        resp = self.call(lobby())
        self.assertEqual(resp["statusCode"], 409)
        self.assertEqual(len(fake.calls), 1)

class TestStartGameGuard(unittest.TestCase):
    """Once the game is Running the roster is frozen, so an erased joiner has no way back."""

    def setUp(self):
        self.real_table = game_module.table

    def tearDown(self):
        game_module.table = self.real_table

    def test_start_is_guarded_on_last_modified(self):
        game_module.table = fake = FakeTable()
        self.assertTrue(game_module.start_game(lobby()))

        call = fake.calls[0]
        self.assertEqual(call['ConditionExpression'], "last_modified = :lm")
        self.assertEqual(call['ExpressionAttributeValues'][':lm'], decimal.Decimal("1000"))

    def test_lost_race_returns_false(self):
        game_module.table = FakeTable(error_code='ConditionalCheckFailedException', fail_times=1)
        self.assertFalse(game_module.start_game(lobby()))

    def test_other_client_errors_propagate(self):
        game_module.table = FakeTable(error_code='ProvisionedThroughputExceededException', fail_times=1)
        with self.assertRaises(ClientError):
            game_module.start_game(lobby())


if __name__ == "__main__":
    unittest.main()
