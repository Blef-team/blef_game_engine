# Unit tests for shared input parsing helpers.
# No network / AWS needed. Run from the api/ directory:
#   python -m unittest test.test_inputs
# or directly:
#   python test/test_inputs.py
import os
import sys
import unicodedata
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.inputs import parse_team  # noqa: E402
from shared.constants import RuleValues  # noqa: E402


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


class TestInitialCardsRule(unittest.TestCase):

    def parse(self, raw):
        value, error = RuleValues.parse_initial_cards_rule(raw)
        self.assertIsNone(error, error)
        return value

    def test_unset(self):
        for raw in [0, "0", "", "  "]:
            self.assertIsNone(self.parse(raw))

    def test_shared_count_and_random(self):
        self.assertEqual(self.parse("3"), 3)
        self.assertEqual(self.parse("Random"), RuleValues.INITIAL_CARDS_RANDOM)

    def test_named_players(self):
        self.assertEqual(self.parse("Ann:2,Bob_(AI):5"), {"Ann": 2, "Bob_(AI)": 5})

    def test_unparseable(self):
        for raw in ["garbage", "Ann:", "Ann:two", ":3"]:
            _, error = RuleValues.parse_initial_cards_rule(raw)
            self.assertIsNotNone(error, raw)

    def test_decomposed_accent_matches_the_stored_roster(self):
        """Rosters are stored NFC (parse_nickname normalises on join), so a
        decomposed accent must resolve to the same player rather than be
        rejected as absent — and must key the dict in the roster's form."""
        nfd = unicodedata.normalize("NFD", "Café")
        self.assertNotEqual(nfd, "Café")
        rule = self.parse(f"{nfd}:3")
        self.assertEqual(rule, {"Café": 3})
        self.assertIsNone(RuleValues.validate_initial_cards_rule(rule, ["Café"], 5))

    def test_unknown_nickname_is_rejected(self):
        rule = self.parse("Ghost:2")
        error = RuleValues.validate_initial_cards_rule(rule, ["Ann"], 5)
        self.assertIn("Target player not found", error)

    def test_counts_must_fit_max_cards(self):
        for rule in [self.parse("9"), self.parse("Ann:9"), self.parse("Ann:0")]:
            self.assertIn("Initial cards must be between",
                          RuleValues.validate_initial_cards_rule(rule, ["Ann"], 5))

    def test_unset_and_random_skip_validation(self):
        for rule in [None, RuleValues.INITIAL_CARDS_RANDOM]:
            self.assertIsNone(RuleValues.validate_initial_cards_rule(rule, [], 5))


if __name__ == "__main__":
    unittest.main()
