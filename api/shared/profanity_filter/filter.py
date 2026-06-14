"""High-level nickname obscenity check across all configured languages.

Tuned for *nicknames* (short, heavily obfuscated tokens) and biased to precision
-- it should not block a legitimate nickname just because a swear word happens to
be a substring of it in some language.

* Every term and every input go through the same `normalize()`, so leetspeak,
  homoglyphs, spacing, full-width, zero-width and repeats are undone first.
* Most terms match WHOLE-STRING. Because normalization already removes spacing,
  the nickname is a single token, so this is effectively whole-word matching
  ("n1gg45" -> "niggas" still blocks) and a swear inside a real word/name
  (`analysis`, `Caputo`) does NOT match.
* A curated, *validated* "substring-safe" set of strong obscenity roots matches
  ANYWHERE (so `fuckyou`, `xxxfuckxxx`, compounds are caught). A root is only in
  this set if it provably never occurs inside a real clean word or name in any
  supported language -- see `scripts/tune_substring.py`, which generates
  `data/substring_safe.txt` and demotes any root that would cause a collision.
* No-word-boundary scripts (CJK, kana, Hangul, Thai) have no spaces, so terms in
  them always match as substrings (still effectively whole-word).
* Per-line overrides in wordlists: "*term" forces substring, "=term" whole-string.
* The allowlist whitelists the rare name that itself normalizes to an obscenity.
"""

import os

from .matcher import BACKEND, Matcher
from .normalize import normalize

# language code -> human label (also defines load order / coverage)
LANGS = {
    "en": "English", "ar": "Arabic", "bg": "Bulgarian",
    "zh-Hans": "Chinese (Simplified)", "zh-Hant": "Chinese (Traditional)",
    "hr": "Croatian", "cs": "Czech", "fr": "French", "de": "German",
    "hi": "Hindi", "id": "Indonesian", "it": "Italian", "ja": "Japanese",
    "ko": "Korean", "pl": "Polish", "pt": "Portuguese", "ru": "Russian",
    "sk": "Slovak", "es": "Spanish", "th": "Thai", "tr": "Turkish",
    "uk": "Ukrainian", "vi": "Vietnamese",
}

_HERE = os.path.dirname(__file__)
_SEEDS = os.path.join(_HERE, "data", "seeds")
_BUILT = os.path.join(_HERE, "data", "wordlists")
_ALLOW = os.path.join(_HERE, "data", "allowlists")
_SAFE_GEN = os.path.join(_HERE, "data", "substring_safe.txt")       # validated
_SAFE_SEED = os.path.join(_HERE, "data", "substring_safe_seed.txt")  # candidates


def _wordlists_dir():
    """Prefer built (fuller) lists; fall back to the committed seeds."""
    env = os.environ.get("PROFANITY_DATA_DIR")
    if env:
        return env
    if os.path.isdir(_BUILT) and any(f.endswith(".txt") for f in os.listdir(_BUILT)):
        return _BUILT
    return _SEEDS


def _parse_line(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None, None
    if line[0] == "=":
        return line[1:].strip(), "exact"
    if line[0] == "*":
        return line[1:].strip(), "substr"
    return line, None


def _read_norm_set(*paths):
    """Read the first existing file into a set of normalized terms."""
    for path in paths:
        if path and os.path.exists(path):
            out = set()
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    raw, _ = _parse_line(line)
                    n = normalize(raw) if raw else ""
                    if n:
                        out.add(n)
            return out
    return set()


class Filter:
    def __init__(self, wordlists_dir=None, allow_dir=None, safe_path=None):
        self._substr = Matcher()
        self._substr_norms = set()   # dedupe substr terms
        self._exact = {}             # normalized -> (lang, raw)
        self._allow_substr = Matcher()
        self._allow_exact = set()
        self.backend = BACKEND
        self.loaded = {}             # lang -> term count
        # roots safe to match anywhere (validated); seed file is the fallback
        self._safe = _read_norm_set(safe_path, _SAFE_GEN, _SAFE_SEED)
        self._load(wordlists_dir or _wordlists_dir(), allow_dir or _ALLOW)
        # ensure every safe root is matchable even if no wordlist contained it
        # (threats/hate phrases and compounds live only in the safe set)
        for norm in self._safe:
            self._add_substr(norm, ("rule", norm))
        self._substr.build()
        self._allow_substr.build()

    # -- loading ---------------------------------------------------------------
    def _add_substr(self, norm, payload):
        if norm and norm not in self._substr_norms:
            self._substr.add(norm, payload)
            self._substr_norms.add(norm)

    def _add_term(self, raw, lang, mode):
        norm = normalize(raw)
        if not norm:
            return
        if mode is None:
            # Substring only for terms validated safe to match anywhere
            # (see scripts/tune_substring.py); everything else whole-string,
            # which keeps real names and clean words from matching by accident.
            mode = "substr" if norm in self._safe else "exact"
        if mode == "substr":
            self._add_substr(norm, (lang, raw))
        else:
            self._exact.setdefault(norm, (lang, raw))
        self.loaded[lang] = self.loaded.get(lang, 0) + 1

    def _load(self, wordlists_dir, allow_dir):
        for lang in LANGS:
            path = os.path.join(wordlists_dir, lang + ".txt")
            if not os.path.exists(path):  # built dir may lack curated-only langs
                path = os.path.join(_SEEDS, lang + ".txt")
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    raw, mode = _parse_line(line)
                    if raw:
                        self._add_term(raw, lang, mode)
        if os.path.isdir(allow_dir):
            for fn in sorted(os.listdir(allow_dir)):
                if not fn.endswith(".txt"):
                    continue
                with open(os.path.join(allow_dir, fn), encoding="utf-8") as fh:
                    for line in fh:
                        raw, mode = _parse_line(line)
                        norm = normalize(raw) if raw else ""
                        if not norm:
                            continue
                        # always whitelist the exact string; only extend to
                        # substring-coverage when the entry is NOT itself an
                        # obscenity ("=term" => whole-string allow only).
                        self._allow_exact.add(norm)
                        if mode != "exact":
                            self._allow_substr.add(norm, norm)

    # -- querying --------------------------------------------------------------
    def check(self, name):
        norm = normalize(name)
        result = {
            "input": name, "normalized": norm,
            "offensive": False, "matches": [], "backend": self.backend,
        }
        if not norm:
            return result
        if norm in self._allow_exact:
            result["allowed"] = True
            return result
        if norm in self._exact:
            lang, raw = self._exact[norm]
            result["offensive"] = True
            result["matches"].append(
                {"term": raw, "lang": lang, "language": LANGS.get(lang, lang),
                 "mode": "exact", "span": [0, len(norm)]}
            )
            return result
        allow_spans = self._allow_substr.find(norm)
        for start, end, (lang, raw) in self._substr.find(norm):
            if any(a_s <= start and end <= a_e for a_s, a_e, _ in allow_spans):
                continue
            result["offensive"] = True
            result["matches"].append(
                {"term": raw, "lang": lang, "language": LANGS.get(lang, lang),
                 "mode": "substr", "span": [start, end]}
            )
        return result

    def is_offensive(self, name):
        return self.check(name)["offensive"]


# Module-level singleton: built once per warm Lambda container (and captured by
# SnapStart's post-init snapshot), so the cold-start cost is paid at most once.
_default = None


def get_filter():
    global _default
    if _default is None:
        _default = Filter()
    return _default


def is_offensive(name):
    return get_filter().is_offensive(name)


def check(name):
    return get_filter().check(name)
