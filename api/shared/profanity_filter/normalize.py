"""Unicode-aware normalization for nickname obscenity matching.

The same `normalize()` is applied to BOTH the wordlists and the input. That is
what makes homoglyph attacks collapse: a Cyrillic-disguised slur and the real
slur produce the same skeleton, so a single dictionary entry catches both.

Pipeline:
  1. strip zero-width / bidi / control / variation-selector characters
  2. NFKC  (fullwidth, ligatures, compatibility forms -> canonical)
  3. casefold  (Unicode-aware lowercasing)
  4. strip combining marks -- script-aware: only for Latin/Cyrillic/Greek, where
     they are decorative diacritics; Indic/Thai/Arabic marks are preserved
     because they change the word's identity.
  5. fold confusables  (Cyrillic/Greek/stroke homoglyphs -> ASCII)
  6. fold leetspeak  (4->a, 1->i, $->s, ...)
  7. drop separators / punctuation / symbols (keep letters, marks, digits) ->
     defeats "n i g g a" and "n.i.g.g.a"
  8. collapse 3+ repeats  (fuuuuck -> fuck)
"""

import re
import unicodedata

from .confusables import CONFUSABLES

# Zero-width, bidi overrides, soft hyphen, Mongolian vowel sep, BOM, word joiner,
# and variation selectors -- all classic invisible-character evasion vectors.
# Built from explicit codepoints so the source stays free of literal invisibles.
_IGNORABLE_CODEPOINTS = (
    [0x00AD, 0x180E, 0xFEFF]
    + list(range(0x200B, 0x2010))   # ZWSP..RLM
    + list(range(0x202A, 0x202F))   # bidi embeddings / overrides
    + list(range(0x2060, 0x2070))   # word joiner, invisible operators
    + list(range(0xFE00, 0xFE10))   # variation selectors
)
_IGNORABLE = re.compile("[" + "".join(map(chr, _IGNORABLE_CODEPOINTS)) + "]")

# Conservative leetspeak folds (kept close to the original to limit false
# positives from legitimate digits in names).
_LEET = str.maketrans({
    "@": "a", "4": "a", "3": "e", "1": "i", "!": "i",
    "0": "o", "$": "s", "5": "s", "7": "t",
})

_CONF_TABLE = {ord(k): v for k, v in CONFUSABLES.items()}

_REPEATS = re.compile(r"(.)\1{2,}")


def _diacritic_script(ch):
    """True if combining marks on this base are decorative (safe to drop)."""
    o = ord(ch)
    return (
        0x0041 <= o <= 0x024F      # Latin (+ Extended-A/B)
        or 0x0370 <= o <= 0x03FF   # Greek
        or 0x0400 <= o <= 0x04FF   # Cyrillic
        or 0x1E00 <= o <= 0x1EFF   # Latin Extended Additional (Vietnamese etc.)
    )


def _strip_marks(s):
    """Drop combining marks, but only those attached to Latin/Cyrillic/Greek."""
    out = []
    drop_following = False
    for ch in unicodedata.normalize("NFD", s):
        if unicodedata.category(ch).startswith("M"):
            if not drop_following:
                out.append(ch)
        else:
            drop_following = _diacritic_script(ch)
            out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))


def _keep_meaningful(s):
    out = []
    for ch in s:
        cat = unicodedata.category(ch)
        if cat[0] in ("L", "M") or cat == "Nd":
            out.append(ch)
    return "".join(out)


def normalize(name):
    if not name:
        return ""
    s = _IGNORABLE.sub("", str(name))
    s = unicodedata.normalize("NFKC", s)
    s = s.casefold()
    s = _strip_marks(s)
    s = s.translate(_CONF_TABLE)
    s = s.translate(_LEET)
    s = _keep_meaningful(s)
    s = _REPEATS.sub(r"\1", s)
    return s


# Scripts with no inter-word spacing: a 2-char token is already a whole word, so
# short terms in these scripts are still safe to match as substrings.
def has_no_boundary_script(s):
    for ch in s:
        o = ord(ch)
        if (
            0x4E00 <= o <= 0x9FFF      # CJK Unified
            or 0x3400 <= o <= 0x4DBF   # CJK Extension A
            or 0x3040 <= o <= 0x30FF   # Hiragana + Katakana
            or 0xAC00 <= o <= 0xD7A3   # Hangul syllables
            or 0x0E00 <= o <= 0x0E7F   # Thai
        ):
            return True
    return False
