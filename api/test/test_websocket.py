# Unit tests for shared.websocket's broadcast helper.
# No network / AWS needed (the management API and the table are stubbed). Run from
# the api/ directory:
#   python test/test_websocket.py
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

CONNECTION_ID = "Y_dxWcOZrPECECg="


class GoneException(Exception):
    pass


class FakeApiGateway:
    exceptions = type("Exceptions", (), {"GoneException": GoneException})

    def __init__(self, raises=None):
        self.raises = raises
        self.calls = []

    def post_to_connection(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise self.raises("boom")


class FakeTable:
    def __init__(self):
        self.deleted = []

    def delete_item(self, **kwargs):
        self.deleted.append(kwargs["Key"])


class TestPostToConnection(unittest.TestCase):

    def setUp(self):
        self.real_api, self.real_table = ws.apigateway, ws.websocket_table
        ws.websocket_table = self.table = FakeTable()

    def tearDown(self):
        ws.apigateway, ws.websocket_table = self.real_api, self.real_table

    def post(self):
        return ws.post_to_connection({"status": "Running"}, CONNECTION_ID)

    def test_delivers_the_payload_wrapped_in_a_200(self):
        ws.apigateway = fake = FakeApiGateway()
        self.post()

        call = fake.calls[0]
        self.assertEqual(call["ConnectionId"], CONNECTION_ID)
        self.assertEqual(json.loads(json.loads(call["Data"])["body"])["status"], "Running")
        self.assertEqual(self.table.deleted, [])

    def test_gone_connection_is_forgotten(self):
        # Otherwise a client that dropped costs a failed post on every future
        # broadcast, for as long as the game is still being played.
        ws.apigateway = FakeApiGateway(raises=GoneException)
        self.post()
        self.assertEqual(self.table.deleted, [{"connection_id": CONNECTION_ID}])

    def test_other_failures_keep_the_connection(self):
        # A throttle or a transient error must never cut a live watcher off.
        for err in (RuntimeError, ValueError, ConnectionError):
            with self.subTest(error=err.__name__):
                ws.apigateway = FakeApiGateway(raises=err)
                self.post()
                self.assertEqual(self.table.deleted, [])

    def test_a_failure_never_aborts_the_rest_of_the_broadcast(self):
        for err in (GoneException, RuntimeError):
            with self.subTest(error=err.__name__):
                ws.apigateway = FakeApiGateway(raises=err)
                self.assertTrue(self.post())


class TestEndpoint(unittest.TestCase):

    def test_endpoint_is_derived_not_looked_up(self):
        # Building it from the API id keeps the API Gateway control plane off the
        # cold-start path, where a throttle would fail every invocation.
        self.assertEqual(ws.endpoint_url, "https://abc123.execute-api.eu-west-2.amazonaws.com/production")


if __name__ == "__main__":
    unittest.main()
