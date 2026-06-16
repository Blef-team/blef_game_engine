"""Multi-pattern substring matcher.

Uses the C-accelerated `pyahocorasick` if it is importable (drop it in the Lambda
layer for big dictionaries / lower memory), otherwise falls back to a compact
pure-Python Aho-Corasick automaton so the package has zero hard dependencies and
the layer stays architecture-independent.

Both backends expose the same tiny interface via `Matcher`:
    m = Matcher(); m.add(term, payload); ...; m.build()
    m.find(text)  -> list of (start, end, payload)
    m.any(text)   -> bool
"""

from collections import deque

try:
    import ahocorasick as _ahocorasick

    BACKEND = "pyahocorasick"
except Exception:  # pragma: no cover - exercised by the pure-python path
    _ahocorasick = None
    BACKEND = "python"


class _PyAutomaton:
    """Minimal Aho-Corasick. API mirrors the subset of pyahocorasick we use."""

    def __init__(self):
        self._goto = [{}]
        self._fail = [0]
        self._out = [[]]  # node -> list of stored values

    def add_word(self, word, value):
        node = 0
        for ch in word:
            nxt = self._goto[node].get(ch)
            if nxt is None:
                nxt = len(self._goto)
                self._goto.append({})
                self._fail.append(0)
                self._out.append([])
                self._goto[node][ch] = nxt
            node = nxt
        self._out[node].append(value)

    def make_automaton(self):
        q = deque()
        for nxt in self._goto[0].values():
            self._fail[nxt] = 0
            q.append(nxt)
        while q:
            r = q.popleft()
            for ch, u in self._goto[r].items():
                q.append(u)
                f = self._fail[r]
                while f and ch not in self._goto[f]:
                    f = self._fail[f]
                self._fail[u] = self._goto[f].get(ch, 0) if f else self._goto[0].get(ch, 0)
                if self._fail[u] == u:
                    self._fail[u] = 0
                self._out[u].extend(self._out[self._fail[u]])

    def iter(self, text):
        node = 0
        for i, ch in enumerate(text):
            while node and ch not in self._goto[node]:
                node = self._fail[node]
            node = self._goto[node].get(ch, 0)
            for value in self._out[node]:
                yield i, value


class Matcher:
    def __init__(self):
        self._a = _ahocorasick.Automaton() if _ahocorasick else _PyAutomaton()
        self._n = 0

    def add(self, term, payload):
        if term:
            # value bundles the length so find() can recover the start offset
            self._a.add_word(term, (len(term), payload))
            self._n += 1

    def build(self):
        if self._n:
            self._a.make_automaton()

    def find(self, text):
        if not self._n:
            return []
        out = []
        for end_index, (length, payload) in self._a.iter(text):
            start = end_index - length + 1
            out.append((start, end_index + 1, payload))
        return out

    def any(self, text):
        if not self._n:
            return False
        for _ in self._a.iter(text):
            return True
        return False
