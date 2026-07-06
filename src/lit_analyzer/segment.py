"""Deterministic text segmentation.

No cleverness: split into words and sentences with regexes, and cut the text
into N word-balanced windows for arc sampling. Good enough for phase 0; a
sentence-boundary model is a later refinement (see the design doc).
"""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
# Split on sentence-final punctuation followed by whitespace. Crude on
# abbreviations ("Mr. Toad") but honest and dependency-free.
_SENTENCE_RE = re.compile(r"[^.!?]+(?:[.!?]+|$)")


def words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.findall(text) if s.strip()]


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def windows(text: str, n: int) -> list[str]:
    """Cut text into ``n`` windows of (near-)equal word count, in order.

    Windows are built from whole words so no token is split or dropped. If the
    text has fewer than ``n`` words, some trailing windows come back empty and
    are omitted — the caller gets ``min(n, word_count)`` windows.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    toks = words(text)
    if not toks:
        return []
    per = len(toks) / n
    out: list[str] = []
    for i in range(n):
        lo = int(round(i * per))
        hi = int(round((i + 1) * per))
        chunk = toks[lo:hi]
        if chunk:
            out.append(" ".join(chunk))
    return out
