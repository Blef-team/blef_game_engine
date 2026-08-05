# Unit tests for the AI agent orchestrator's routing.
# No network / AWS needed (the Lambda client is stubbed). Run from the api/ directory:
#   python test/test_aiagent_orchestrator.py
import os
import sys
import importlib
import json
import unittest

os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-2")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
orchestrator = importlib.import_module("aiagent-orchestrator")  # noqa: E402


class ResourceNotFoundException(Exception):
    pass


class FakeLambdaClient:
    """Records invocations, optionally failing them the way Invoke reports a missing function."""

    exceptions = type("Exceptions", (), {"ResourceNotFoundException": ResourceNotFoundException})

    def __init__(self, missing=False):
        self.missing = missing
        self.calls = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        if self.missing:
            raise ResourceNotFoundException("Function not found")
        return {"StatusCode": 202}

    def get_function(self, **kwargs):
        raise AssertionError("The orchestrator must not look the function up before invoking it")


def game(agent="conservative", nickname="Dazhbog_(AI)"):
    return {
        "game_uuid": "11111111-1111-1111-1111-111111111111",
        "cp_nickname": nickname,
        "players": [{"uuid": "u1", "nickname": nickname, "ai_agent": agent}],
    }


class TestCallAiagent(unittest.TestCase):

    def setUp(self):
        self.real_client = orchestrator.lambda_client

    def tearDown(self):
        orchestrator.lambda_client = self.real_client

    def test_invokes_the_matching_agent_asynchronously(self):
        orchestrator.lambda_client = fake = FakeLambdaClient()
        orchestrator.call_aiagent(game())

        self.assertEqual(len(fake.calls), 1)
        call = fake.calls[0]
        self.assertEqual(call["FunctionName"], "blef-aiagent-conservative")
        self.assertEqual(call["InvocationType"], "Event")
        self.assertEqual(json.loads(call["Payload"])["cp_nickname"], "Dazhbog_(AI)")

    def test_missing_function_is_swallowed_not_raised(self):
        # A missing agent must not fail the whole SQS batch.
        orchestrator.lambda_client = FakeLambdaClient(missing=True)
        self.assertIsNone(orchestrator.call_aiagent(game()))

    def test_unusable_agent_name_is_never_interpolated(self):
        orchestrator.lambda_client = fake = FakeLambdaClient()
        for bad in ["../../etc", "has space", "semi;colon", "", None]:
            orchestrator.call_aiagent(game(agent=bad))
        self.assertEqual(fake.calls, [])


class TestHandler(unittest.TestCase):

    def setUp(self):
        self.real_client = orchestrator.lambda_client

    def tearDown(self):
        orchestrator.lambda_client = self.real_client

    def test_processes_every_record_in_the_batch(self):
        orchestrator.lambda_client = fake = FakeLambdaClient()
        event = {"Records": [{"body": json.dumps(game())}, {"body": json.dumps(game(agent="nfsp"))}]}

        resp = orchestrator.lambda_handler(event, None)

        self.assertEqual(resp["statusCode"], 200)
        self.assertEqual([c["FunctionName"] for c in fake.calls],
                         ["blef-aiagent-conservative", "blef-aiagent-nfsp"])

    def test_unparseable_record_is_skipped(self):
        orchestrator.lambda_client = fake = FakeLambdaClient()
        resp = orchestrator.lambda_handler({"Records": [{"body": "not json"}, {}]}, None)

        self.assertEqual(resp["statusCode"], 200)
        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()
