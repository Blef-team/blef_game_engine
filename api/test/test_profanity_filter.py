# Unit tests for the nickname obscenity filter + the 422 response helper.
# No network / AWS needed. Run from the api/ directory:
#   python -m unittest test.test_profanity_filter
# or directly:
#   python test/test_profanity_filter.py
import os
import sys
import json
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.profanity_filter import is_offensive          # noqa: E402
from shared.response import nickname_rejected_payload      # noqa: E402


class TestProfanityFilter(unittest.TestCase):

    def test_blocks_obscene(self):
        # all pass the handlers' ^[a-zA-Z]\w*$ format rule, yet are obscene
        for nick in ["fuckyou", "n1gg45", "kurwa123", "asshole", "fuckface"]:
            self.assertTrue(is_offensive(nick), f"{nick} should be blocked")

    def test_allows_clean_names(self):
        # real names that merely contain a swear substring must still pass
        for nick in ["Adrian", "Caputo", "Sukarno", "Dickson", "Scunthorpe", "Jeb"]:
            self.assertFalse(is_offensive(nick), f"{nick} should be allowed")

    def test_obfuscation_still_caught(self):
        self.assertTrue(is_offensive("n1gg45"))          # leetspeak -> niggas
        self.assertTrue(is_offensive("fuсk"))       # Cyrillic 'с' homoglyph -> fuck

    def test_422_payload_shape(self):
        r = nickname_rejected_payload(reason="profanity")
        self.assertEqual(r["statusCode"], 422)
        body = json.loads(r["body"])
        self.assertEqual(body["field"], "nickname")
        self.assertEqual(body["reason"], "profanity")


if __name__ == "__main__":
    unittest.main(verbosity=2)
