# Unit tests for shared.db.update_players_conditionally.
# No network / AWS needed (the DynamoDB table is stubbed). Run from the api/ directory:
#   python -m unittest test.test_db
# or directly:
#   python test/test_db.py
import os
import sys
import decimal
import unittest

os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-2")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import shared.db as db  # noqa: E402
from botocore.exceptions import ClientError  # noqa: E402


class FakeTable:
    def __init__(self, error_code=None):
        self.error_code = error_code
        self.calls = []

    def update_item(self, **kwargs):
        self.calls.append(kwargs)
        if self.error_code:
            raise ClientError({'Error': {'Code': self.error_code}}, 'UpdateItem')


class TestUpdatePlayersConditionally(unittest.TestCase):

    def setUp(self):
        self.real_table = db.table
        self.players = [{"nickname": "A"}, {"nickname": "B"}]
        self.last_modified = decimal.Decimal("1722600000.0")

    def tearDown(self):
        db.table = self.real_table

    def test_success_returns_true_and_guards_on_last_modified(self):
        db.table = fake = FakeTable()
        result = db.update_players_conditionally("uuid-1", self.players, self.last_modified)
        self.assertTrue(result)

        call = fake.calls[0]
        self.assertEqual(call['Key'], {'game_uuid': "uuid-1"})
        self.assertEqual(call['ConditionExpression'], "last_modified = :lm")
        self.assertEqual(call['ExpressionAttributeValues'][':lm'], self.last_modified)
        self.assertEqual(call['ExpressionAttributeValues'][':players'], self.players)
        self.assertNotIn('ExpressionAttributeNames', call)

    def test_extra_attributes_ride_along_via_name_placeholders(self):
        db.table = fake = FakeTable()
        db.update_players_conditionally(
            "uuid-1", self.players, self.last_modified,
            rules={"deck_size": 24}, max_cards=5, admin_nickname=None)

        call = fake.calls[0]
        names = call['ExpressionAttributeNames']
        values = call['ExpressionAttributeValues']
        # Every extra attribute is written through a name placeholder (so
        # reserved words like "rules" are safe) with a matching value.
        written = {names[placeholder]: values[placeholder.replace('#', ':')]
                   for placeholder in names}
        self.assertEqual(written, {"rules": {"deck_size": 24}, "max_cards": 5, "admin_nickname": None})
        for placeholder in names:
            self.assertIn(f"{placeholder} = {placeholder.replace('#', ':')}", call['UpdateExpression'])

    def test_lost_race_returns_false(self):
        db.table = FakeTable(error_code='ConditionalCheckFailedException')
        result = db.update_players_conditionally("uuid-1", self.players, self.last_modified)
        self.assertFalse(result)

    def test_other_client_errors_propagate(self):
        db.table = FakeTable(error_code='ProvisionedThroughputExceededException')
        with self.assertRaises(ClientError):
            db.update_players_conditionally("uuid-1", self.players, self.last_modified)


if __name__ == "__main__":
    unittest.main()
