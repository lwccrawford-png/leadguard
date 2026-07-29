import re

_WORD_RE = re.compile(r"[a-zA-Z]+")

# Deliberately not a real stemmer (no new dependency) — just enough suffix-stripping to stop
# "refunds" vs "refund" or "cancelling" vs "cancel" from being treated as unrelated tokens by
# plain TF-IDF, which has no notion of word forms at all. Good enough for short business-facing
# questions; not a substitute for real NLP if content gets much more varied.
_SUFFIXES = ("ing", "edly", "ed", "es", "s")


def _stem(token: str) -> str:
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> list:
    return [_stem(t) for t in _WORD_RE.findall(text.lower())]
