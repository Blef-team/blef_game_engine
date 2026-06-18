# Unit tests for avatar vocabulary + validation (pure, no network / no AWS).
import os
import sys
import unittest

# Make the api/ dir importable so `shared.constants` resolves regardless of cwd.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.constants import AvatarSlots, random_avatar, validate_avatar

SLOTS = set(AvatarSlots.OPTIONS)


def _is_valid_avatar(avatar):
    return (
        isinstance(avatar, dict)
        and set(avatar) == SLOTS
        and all(avatar[slot] in AvatarSlots.OPTIONS[slot] for slot in SLOTS)
    )


class TestAvatarValidation(unittest.TestCase):

    def test_random_avatar_is_valid(self):
        self.assertTrue(_is_valid_avatar(random_avatar()))

    def test_empty_body_fills_all_slots_randomly(self):
        avatar, err = validate_avatar({})
        self.assertIsNone(err)
        self.assertTrue(_is_valid_avatar(avatar))

    def test_all_slots_provided_are_preserved(self):
        body = {
            "avatar_base": "wolf",
            "avatar_cloth": "poppy",
            "avatar_eyes": "narrow",
            "avatar_hat": "wreath",
        }
        avatar, err = validate_avatar(body)
        self.assertIsNone(err)
        self.assertEqual(
            avatar,
            {"base": "wolf", "cloth": "poppy", "eyes": "narrow", "hat": "wreath"},
        )

    def test_partial_input_preserves_given_and_fills_rest(self):
        avatar, err = validate_avatar({"avatar_hat": "antlers"})
        self.assertIsNone(err)
        self.assertEqual(avatar["hat"], "antlers")
        self.assertTrue(_is_valid_avatar(avatar))

    def test_explicit_bare_hat_is_not_randomised(self):
        # "bare" is a real token (bare-headed); it must be respected, not rerolled.
        avatar, err = validate_avatar({"avatar_hat": "bare"})
        self.assertIsNone(err)
        self.assertEqual(avatar["hat"], "bare")

    def test_invalid_token_is_rejected(self):
        avatar, err = validate_avatar({"avatar_hat": "tophat"})
        self.assertIsNone(avatar)
        self.assertIn("avatar_hat", err)

    def test_non_string_value_is_rejected(self):
        avatar, err = validate_avatar({"avatar_hat": 3})
        self.assertIsNone(avatar)
        self.assertIn("avatar_hat", err)

    def test_unrelated_params_are_ignored(self):
        body = {"nickname": "x", "avatar_weapon": "sword"}
        avatar, err = validate_avatar(body)
        self.assertIsNone(err)
        self.assertTrue(_is_valid_avatar(avatar))


if __name__ == "__main__":
    unittest.main(verbosity=2)
