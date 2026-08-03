# Unit tests for response payloads whose exact shape is API surface.
# No network / AWS needed. Run from the api/ directory:
#   python test/test_response.py
import os
import sys
import json
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.response import conflict_payload, nickname_rejected_payload  # noqa: E402


class TestConflictPayload(unittest.TestCase):

    def setUp(self):
        self.payload = conflict_payload()
        self.body = json.loads(self.payload["body"])

    def test_status_is_409(self):
        self.assertEqual(self.payload["statusCode"], 409)

    def test_message_is_stable(self):
        # Published wording, matchable by clients: a failure here means an API
        # change, not a stale test. Reword only with a deliberate release.
        self.assertEqual(self.body["error"], "The game state changed.")


class TestNicknameRejectedPayload(unittest.TestCase):

    def test_carries_a_machine_readable_reason(self):
        body = json.loads(nickname_rejected_payload()["body"])
        self.assertEqual(body["reason"], "profanity")
        self.assertEqual(body["field"], "nickname")


if __name__ == "__main__":
    unittest.main()
