# Unit tests for play.update_in_dynamodb's error classification.
# No network / AWS needed (the DynamoDB table is stubbed). Run from the api/ directory:
#   python test/test_play.py
import os
import sys
import decimal
import unittest

os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-2")
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
                     decimal.Decimal("2000"), decimal.Decimal("1000"))

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


if __name__ == "__main__":
    unittest.main()
