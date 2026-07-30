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

    def test_handler_change_rules_initial_cards(self):
        """Tests the initial_cards rule: its three forms, unset, and validation."""
        url = f"{BASE_URL}/games/{self.game_uuid}/change-rules"
        state_url = f"{BASE_URL}/games/{self.game_uuid}"

        def rules():
            return self.session.get(state_url, params={"player_uuid": self.admin_uuid}).json()["rules"]

        # A shared count applies to everyone.
        resp = self.session.get(url, params={"admin_uuid": self.admin_uuid, "initial_cards": 2})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(int(rules()["initial_cards"]), 2)

        # "random" is stored as-is and resolved per player at start.
        resp = self.session.get(url, params={"admin_uuid": self.admin_uuid, "initial_cards": "random"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(rules()["initial_cards"], "random")

        # Named players — the handicap / challenge form.
        resp = self.session.get(url, params={"admin_uuid": self.admin_uuid,
                                             "initial_cards": "AdminUser:3"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(int(rules()["initial_cards"]["AdminUser"]), 3)

        # 0 clears it.
        resp = self.session.get(url, params={"admin_uuid": self.admin_uuid, "initial_cards": 0})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("initial_cards", rules())

        # Nicknames must already be in the game.
        resp = self.session.get(url, params={"admin_uuid": self.admin_uuid,
                                             "initial_cards": "NoSuchPlayer:2"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Target player not found", resp.json().get("error", ""))

        # Unparseable declarations are rejected.
        resp = self.session.get(url, params={"admin_uuid": self.admin_uuid, "initial_cards": "garbage"})
        self.assertEqual(resp.status_code, 400)

        # Counts above max_cards are refused, not clamped.
        resp = self.session.get(url, params={"admin_uuid": self.admin_uuid, "initial_cards": 99})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Initial cards must be between", resp.json().get("error", ""))

    def test_handler_change_rules_initial_cards_is_order_independent(self):
        """The feasibility check must see the settled rules, not whatever order
        the parameters arrived in. A 24-card deck allows fewer cards per player
        than a 32-card one, so the same pair of rules must give the same answer
        both ways round."""
        url = f"{BASE_URL}/games/{self.game_uuid}/change-rules"

        forward = self.session.get(url, params={"admin_uuid": self.admin_uuid,
                                                "deck_size": 24, "initial_cards": 11})
        self.session.get(url, params={"admin_uuid": self.admin_uuid, "initial_cards": 0})
        backward = self.session.get(url, params={"admin_uuid": self.admin_uuid,
                                                 "initial_cards": 11, "deck_size": 24})
        self.assertEqual(forward.status_code, backward.status_code,
                         "initial_cards validation depends on parameter order")

    def test_handler_change_rules_stale_initial_cards_does_not_block_other_rules(self):
        """A rule that was valid when set can go stale as the roster moves. It
        must never lock the game's other rules: only a request that actually
        sets initial_cards is validated, and start_game clamps the rest."""
        url = f"{BASE_URL}/games/{self.game_uuid}/change-rules"
        join_url = f"{BASE_URL}/games/{self.game_uuid}/join"

        # A named player leaves. Cara keeps the game at two seats, so it is the
        # roster check that would fire rather than max_cards collapsing to 0.
        bob_uuid = self.session.get(join_url, params={"nickname": "Bob"}).json()["player_uuid"]
        self.session.get(join_url, params={"nickname": "Cara"})
        resp = self.session.get(url, params={"admin_uuid": self.admin_uuid,
                                             "initial_cards": "Bob:3"})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.session.get(f"{BASE_URL}/games/{self.game_uuid}/remove-player",
                         params={"player_uuid": bob_uuid, "nickname": "Bob"})
        resp = self.session.get(url, params={"admin_uuid": self.admin_uuid, "deck_size": 32})
        self.assertEqual(resp.status_code, 200,
                         f"a departed player's seed blocked an unrelated rule change: {resp.text}")

        # The roster grows, so max_cards falls below a count that was feasible.
        resp = self.session.get(url, params={"admin_uuid": self.admin_uuid,
                                             "deck_size": 24, "initial_cards": 8})
        self.assertEqual(resp.status_code, 200, resp.text)  # 2 seats on 24 cards allows 11
        for nickname in ["Dana", "Efim", "Fola", "Gita"]:      # 5+ seats allows only 4
            self.session.get(join_url, params={"nickname": nickname})
        resp = self.session.get(url, params={"admin_uuid": self.admin_uuid, "deck_size": 32})
        self.assertEqual(resp.status_code, 200,
                         f"an over-max seed blocked an unrelated rule change: {resp.text}")

    def test_handler_change_rules_initial_cards_unsets_readiness(self):
        """Changing the opening hands changes the fairness players agreed to, so
        it must re-ask for readiness — the treatment team changes already get."""
        url = f"{BASE_URL}/games/{self.game_uuid}/change-rules"
        self.session.get(f"{BASE_URL}/games/{self.game_uuid}/join", params={"nickname": "Bob"})

        # Only the admin declares ready, or the game would start on the spot.
        resp = self.session.get(f"{BASE_URL}/games/{self.game_uuid}/set-readiness",
                                params={"player_uuid": self.admin_uuid, "ready": "True"})
        self.assertEqual(resp.status_code, 200, resp.text)

        def admin_is_ready():
            players = self.session.get(f"{BASE_URL}/games/{self.game_uuid}",
                                       params={"player_uuid": self.admin_uuid}).json()["players"]
            return next(p for p in players if p["nickname"] == "AdminUser").get("ready")

        self.assertTrue(admin_is_ready(), "setup failed: readiness never took")
        resp = self.session.get(url, params={"admin_uuid": self.admin_uuid, "initial_cards": 2})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertFalse(admin_is_ready(), "initial_cards changed without re-asking for readiness")

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

    # ---------------------------------------------------------
    # JOINING STRAIGHT INTO A TEAM
    # ---------------------------------------------------------

    def _player(self, game_uuid, nickname):
        state = self.session.get(f"{BASE_URL}/games/{game_uuid}", params={"player_uuid": self.admin_uuid}).json()
        return next(p for p in state["players"] if p["nickname"] == nickname)

    def test_join_with_team_seats_the_player(self):
        """A team supplied on join is applied without a follow-up change-team call."""
        resp = self.session.get(f"{BASE_URL}/games/{self.game_uuid}/join", params={"nickname": "Teamed", "team": 2})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(self._player(self.game_uuid, "Teamed")["team"], 2)

    def test_join_without_team_is_independent(self):
        """Omitting the team keeps the previous behaviour: an independent player."""
        resp = self.session.get(f"{BASE_URL}/games/{self.game_uuid}/join", params={"nickname": "Loner"})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIsNone(self._player(self.game_uuid, "Loner")["team"])

    def test_join_with_team_resets_human_readiness(self):
        """Joining into a team is equivalent to join + change-team, so it unreadies humans."""
        self.session.get(f"{BASE_URL}/games/{self.game_uuid}/join", params={"nickname": "Early"})
        self.session.get(f"{BASE_URL}/games/{self.game_uuid}/join", params={"nickname": "Teamed", "team": 3})
        self.assertFalse(self._player(self.game_uuid, "Early")["ready"])

    def test_create_with_nickname_and_team(self):
        """The creator can claim a team in the same call."""
        resp = self.session.get(f"{BASE_URL}/games/create", params={"nickname": "Founder", "team": 1})
        self.assertEqual(resp.status_code, 200, resp.text)
        state = self.session.get(f"{BASE_URL}/games/{resp.json()['game_uuid']}").json()
        self.assertEqual(state["players"][0]["team"], 1)

    def test_create_with_team_but_no_nickname_rejected(self):
        """A team without a nickname creates no player, so it is an error rather than a silent no-op."""
        resp = self.session.get(f"{BASE_URL}/games/create", params={"team": 1})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("only be set when joining with a nickname", resp.json().get("error", ""))

    def test_invalid_team_rejected(self):
        """Out-of-range and non-integer teams are rejected on both entry points."""
        for params in [{"nickname": "Bad1", "team": 5}, {"nickname": "Bad2", "team": "green"}]:
            with self.subTest(params=params):
                resp = self.session.get(f"{BASE_URL}/games/{self.game_uuid}/join", params=params)
                self.assertEqual(resp.status_code, 400, resp.text)
                self.assertIn("Team must be", resp.json().get("error", ""))
        resp = self.session.get(f"{BASE_URL}/games/create", params={"nickname": "Bad3", "team": 9})
        self.assertEqual(resp.status_code, 400, resp.text)

    def test_rejected_team_does_not_consume_the_rematch(self):
        """A rejected team must not leave the previous game pointing at a game
        that was never saved. The rematch link can only be claimed once, so a
        request that fails after claiming it would brick rematches for good."""
        self.session.get(f"{BASE_URL}/games/{self.game_uuid}/join", params={"nickname": "Bob"})

        resp = self.session.get(f"{BASE_URL}/games/create",
                                params={"previous_game_uuid": self.game_uuid,
                                        "previous_player_uuid": self.admin_uuid, "team": 2})
        self.assertEqual(resp.status_code, 400, resp.text)

        # The link must still be free, and a genuine rematch must reach a real game.
        resp = self.session.get(f"{BASE_URL}/games/create",
                                params={"previous_game_uuid": self.game_uuid,
                                        "previous_player_uuid": self.admin_uuid,
                                        "nickname": "AdminUser"})
        self.assertEqual(resp.status_code, 200, resp.text)
        rematch_uuid = resp.json()["game_uuid"]
        state = self.session.get(f"{BASE_URL}/games/{rematch_uuid}")
        self.assertEqual(state.status_code, 200,
                         "the rematch points at a game that does not exist")

if __name__ == "__main__":
    unittest.main(verbosity=2)
