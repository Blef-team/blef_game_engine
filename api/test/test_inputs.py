# Unit tests for shared input parsing helpers.
# No network / AWS needed. Run from the api/ directory:
#   python -m unittest test.test_inputs
# or directly:
#   python test/test_inputs.py
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.inputs import parse_team  # noqa: E402


class TestParseTeam(unittest.TestCase):

    def test_none_means_independent(self):
        self.assertIsNone(parse_team(None))

    def test_valid_teams(self):
        for value in [1, 2, 3, 4, "1", "4"]:
            self.assertEqual(parse_team(value), int(value))

    def test_out_of_range(self):
        for value in [0, 5, -1, "7"]:
            with self.assertRaises(ValueError) as ctx:
                parse_team(value)
            self.assertEqual(str(ctx.exception), "Team must be 1, 2, 3, 4, or null")

    def test_not_an_integer(self):
        for value in ["green", "", [2]]:
            with self.assertRaises(ValueError) as ctx:
                parse_team(value)
            self.assertEqual(str(ctx.exception), "Team must be an integer (1-4) or null")


if __name__ == "__main__":
    unittest.main()
