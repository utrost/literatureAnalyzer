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

# A chapter/part heading: a line that is *only* "Chapter/Part/Book <x>", a lone
# roman numeral, or a lone number (optionally with a trailing title). Conservative
# on purpose — markerless prose stays one chapter rather than over-splitting.
_HEADING_RE = re.compile(
    r"^[ \t]*(?:(?:chapter|part|book)\b[^\n]*|[IVXLCDM]{1,8}\.?|\d{1,3}\.?)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)


def words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.findall(text) if s.strip()]


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def chapter_spans(text: str) -> list[tuple[str | None, str]]:
    """Split text into ``(heading, body)`` chapter spans.

    Markerless text comes back as a single ``(None, text)`` span — the caller
    treats that as a one-chapter (flat) story. Any content before the first
    heading becomes an untitled opening span.
    """
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return [(None, text.strip())]

    spans: list[tuple[str | None, str]] = []
    opening = text[: matches[0].start()].strip()
    if opening:
        spans.append((None, opening))
    for i, m in enumerate(matches):
        heading = m.group(0).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        spans.append((heading, text[start:end].strip()))
    return spans


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
