# Tests several API parameter validation rules
import os
import uuid
import unittest
import unicodedata
import requests

BASE_URL = os.environ.get("BASE_URL").rstrip("/")

class TestAPIValidation(unittest.TestCase):
    
    def setUp(self):
        """Runs before every test: Creates a fresh game and stores the admin credentials."""
        self.session = requests.Session()
        
        # Create a game and join as Admin
        response = self.session.get(f"{BASE_URL}/games/create", params={"nickname": "AdminUser"})
        self.assertEqual(response.status_code, 200, "Failed to create game during setup")
        
        data = response.json()
        self.game_uuid = data["game_uuid"]
        self.admin_uuid = data["player_uuid"]
        
        # Generate some fake UUIDs for negative testing
        self.fake_uuid = str(uuid.uuid4())

    # ---------------------------------------------------------
    # DECORATOR TESTS
    # ---------------------------------------------------------

    def test_decorator_invalid_and_missing_game_uuid(self):
        """Tests base decorator functionality: Game UUID validation."""
        # Malformed UUID format
        resp = self.session.get(f"{BASE_URL}/games/not-a-real-uuid", params={"player_uuid": self.admin_uuid})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid game UUID", resp.json().get("error", ""))

        # Valid UUID format, but game doesn't exist in DB
        resp = self.session.get(f"{BASE_URL}/games/{self.fake_uuid}", params={"player_uuid": self.admin_uuid})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Game does not exist", resp.json().get("error", ""))

    def test_decorator_require_admin(self):
        """Tests the `require_admin=True` parameter (e.g., on change-rules)."""
        url = f"{BASE_URL}/games/{self.game_uuid}/change-rules"
        
        # Missing admin_uuid
        resp = self.session.get(url, params={"time_limit": 60})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Admin UUID missing", resp.json().get("error", ""))

        # Invalid admin_uuid format
        resp = self.session.get(url, params={"admin_uuid": "bad-uuid", "time_limit": 60})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid admin UUID", resp.json().get("error", ""))

        # UUID of a player who is NOT the admin (Join a second player to test)
        join_resp = self.session.get(f"{BASE_URL}/games/{self.game_uuid}/join", params={"nickname": "RegularPlayer"})
        regular_player_uuid = join_resp.json()["player_uuid"]
        
        resp = self.session.get(url, params={"admin_uuid": regular_player_uuid, "time_limit": 60})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Admin UUID does not match", resp.json().get("error", ""))

    def test_decorator_require_player(self):
        """Tests the `require_player=True` parameter (e.g., on set-readiness)."""
        url = f"{BASE_URL}/games/{self.game_uuid}/set-readiness"
        
        # Missing player_uuid
        resp = self.session.get(url, params={"ready": "True"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Player UUID missing", resp.json().get("error", ""))

        # Valid UUID, but player is not in the game
        resp = self.session.get(url, params={"player_uuid": self.fake_uuid, "ready": "True"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("does not match any active player", resp.json().get("error", ""))

    def test_decorator_required_status_and_custom_message(self):
        """Tests `required_status=GameStatus.NOT_STARTED` and `status_error_message`."""
        # Setup: Add a second player and start the game to change its status to RUNNING
        join_resp = self.session.get(f"{BASE_URL}/games/{self.game_uuid}/join", params={"nickname": "PlayerTwo"})
        p2_uuid = join_resp.json()["player_uuid"]
        
        self.session.get(f"{BASE_URL}/games/{self.game_uuid}/set-readiness", params={"player_uuid": self.admin_uuid, "ready": "True"})
        self.session.get(f"{BASE_URL}/games/{self.game_uuid}/set-readiness", params={"player_uuid": p2_uuid, "ready": "True"})
        self.session.get(f"{BASE_URL}/games/{self.game_uuid}/start", params={"admin_uuid": self.admin_uuid})

        # Try to change rules on a running game
        url = f"{BASE_URL}/games/{self.game_uuid}/change-rules"
        resp = self.session.get(url, params={"admin_uuid": self.admin_uuid, "deck_size": 32})
        
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Cannot change rules after the game has started", resp.json().get("error", ""))

    # ---------------------------------------------------------
    # HANDLER LOGIC TESTS
    # ---------------------------------------------------------

    def test_handler_change_rules_types(self):
        """Tests that the simplified change_rules handler properly casts/validates types."""
        url = f"{BASE_URL}/games/{self.game_uuid}/change-rules"
        
        # Pass a string to a rule that expects an integer
        resp = self.session.get(url, params={"admin_uuid": self.admin_uuid, "time_limit": "thirty_seconds"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Every rule must be an integer", resp.json().get("error", ""))

    def test_handler_invite_aiagent(self):
        """Tests the simplified invite-aiagent handler logic."""
        url = f"{BASE_URL}/games/{self.game_uuid}/invite-aiagent"
        
        # Missing agent name
        resp = self.session.get(url, params={"admin_uuid": self.admin_uuid})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Agent name missing", resp.json().get("error", ""))

        # Invalid agent name (not in mapping)
        resp = self.session.get(url, params={"admin_uuid": self.admin_uuid, "agent_name": "Gibberishbog"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid agent_name", resp.json().get("error", ""))

    def test_handler_remove_player_permissions(self):
        """Tests the streamlined remove_player permission logic."""
        # Add a second player
        join_resp = self.session.get(f"{BASE_URL}/games/{self.game_uuid}/join", params={"nickname": "Victim"})
        victim_uuid = join_resp.json()["player_uuid"]

        # Add a third player
        join_resp2 = self.session.get(f"{BASE_URL}/games/{self.game_uuid}/join", params={"nickname": "Bystander"})
        bystander_uuid = join_resp2.json()["player_uuid"]

        url = f"{BASE_URL}/games/{self.game_uuid}/remove-player"

        # Bystander tries to kick Victim (should fail - neither admin nor self)
        resp = self.session.get(url, params={"player_uuid": bystander_uuid, "nickname": "Victim"})
        self.assertEqual(resp.status_code, 403)
        self.assertIn("You do not have permission", resp.json().get("error", ""))

        # Admin kicks Victim (should succeed)
        resp = self.session.get(url, params={"player_uuid": self.admin_uuid, "nickname": "Victim"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("removed successfully", resp.json().get("message", ""))

        # Bystander leaves voluntarily (should succeed - is self)
        resp = self.session.get(url, params={"player_uuid": bystander_uuid, "nickname": "Bystander"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("removed successfully", resp.json().get("message", ""))

    # ---------------------------------------------------------
    # NICKNAME OBSCENITY TESTS (422 + reason)
    # ---------------------------------------------------------

    def test_obscene_nickname_rejected_on_create(self):
        """Atomic create+join with an obscene nickname -> 422 with reason='profanity'."""
        resp = self.session.get(f"{BASE_URL}/games/create", params={"nickname": "kurwa123"})
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json().get("reason"), "profanity")

    def test_obscene_nickname_rejected_on_join(self):
        """Join with an obscene nickname -> 422 with reason='profanity'."""
        resp = self.session.get(f"{BASE_URL}/games/{self.game_uuid}/join", params={"nickname": "fuckface"})
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json().get("reason"), "profanity")

    def test_obscene_nickname_obfuscated_rejected_on_join(self):
        """Leetspeak obfuscation that passes the format rule is still rejected (422)."""
        resp = self.session.get(f"{BASE_URL}/games/{self.game_uuid}/join", params={"nickname": "n1gg45"})
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json().get("reason"), "profanity")

    def test_clean_nickname_with_swear_substring_accepted(self):
        """A clean name that merely contains a swear substring is accepted (no false positive)."""
        resp = self.session.get(f"{BASE_URL}/games/{self.game_uuid}/join", params={"nickname": "Scunthorpe"})
        self.assertEqual(resp.status_code, 200)

    # ---------------------------------------------------------
    # NICKNAME FORMAT TESTS (Unicode letters allowed; specials/doubled-_ rejected)
    # ---------------------------------------------------------

    def test_unicode_nickname_accepted_on_create(self):
        """Atomic create+join with a non-Latin-leading nickname is accepted."""
        resp = self.session.get(f"{BASE_URL}/games/create", params={"nickname": "热的bói"})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIn("player_uuid", resp.json())

    def test_unicode_nickname_accepted_on_join(self):
        """Join with a Cyrillic nickname is accepted."""
        resp = self.session.get(f"{BASE_URL}/games/{self.game_uuid}/join", params={"nickname": "Порвит"})
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_decomposed_accent_nickname_accepted_on_join(self):
        """An NFD (decomposed) accent is NFC-normalised server-side and accepted —
        without normalisation Python's \\w excludes the combining mark and rejects it."""
        nfd_cafe = unicodedata.normalize("NFD", "Café")
        self.assertNotEqual(nfd_cafe, "Café")  # ensure we're actually sending decomposed bytes
        resp = self.session.get(f"{BASE_URL}/games/{self.game_uuid}/join", params={"nickname": nfd_cafe})
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_underscore_separated_nickname_accepted_on_join(self):
        """A single-underscore-separated nickname (the generated Adjective_Animal form) is accepted."""
        resp = self.session.get(f"{BASE_URL}/games/{self.game_uuid}/join", params={"nickname": "Bold_Fox_2"})
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_invalid_nickname_format_rejected_on_create(self):
        """A digit-leading nickname is rejected with the format error on create."""
        resp = self.session.get(f"{BASE_URL}/games/create", params={"nickname": "1foo"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("must start with a letter", resp.json().get("error", ""))

    def test_invalid_nickname_formats_rejected_on_join(self):
        """Leading underscore/digit, doubled or trailing underscores, spaces, specials and
        emoji are all rejected with the format error."""
        for bad in ["_foo", "Bold__Fox", "Bold_", "foo bar", "foo!", "😀foo"]:
            with self.subTest(nickname=bad):
                resp = self.session.get(f"{BASE_URL}/games/{self.game_uuid}/join", params={"nickname": bad})
                self.assertEqual(resp.status_code, 400, f"{bad!r} -> {resp.text}")
                self.assertIn("must start with a letter", resp.json().get("error", ""))

if __name__ == "__main__":
    unittest.main(verbosity=2)
