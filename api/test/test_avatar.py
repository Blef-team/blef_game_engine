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
        avatar, err = validate_avatar({"avatar_mask": "wolf", "avatar_material": "amber"})
        self.assertIsNone(err)
        self.assertEqual(avatar, {"mask": "wolf", "material": "amber"})

    def test_partial_input_preserves_given_and_fills_rest(self):
        # Only the material is supplied; the mask is randomly filled.
        avatar, err = validate_avatar({"avatar_material": "gold"})
        self.assertIsNone(err)
        self.assertEqual(avatar["material"], "gold")
        self.assertTrue(_is_valid_avatar(avatar))

    def test_invalid_token_is_rejected(self):
        avatar, err = validate_avatar({"avatar_material": "plastic"})
        self.assertIsNone(avatar)
        self.assertIn("avatar_material", err)

    def test_non_string_value_is_rejected(self):
        avatar, err = validate_avatar({"avatar_mask": 3})
        self.assertIsNone(avatar)
        self.assertIn("avatar_mask", err)

    def test_unrelated_params_are_ignored(self):
        avatar, err = validate_avatar({"nickname": "x", "avatar_charm": "bells"})
        self.assertIsNone(err)
        self.assertTrue(_is_valid_avatar(avatar))


if __name__ == "__main__":
    unittest.main(verbosity=2)
