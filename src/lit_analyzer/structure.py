"""Structural hierarchy (S0 — book scale).

Turns raw text into a `Section` tree and provides small helpers over it. A flat
short story is a single ``chapter`` Section; a chaptered text becomes a ``book``
whose children are its chapters. Beat→section mapping (populating ``beat_ids``)
needs the LLM beats and is deferred to S1; S0 lays the deterministic structure.

Section ids are stable and align with `segment.chapter_spans` order (``ch1``,
``ch2``, …), so a per-section arc can be attached back to the right node.
"""

from __future__ import annotations

from . import segment
from .schemas import Section

# A real chapter has substantial text. Below this (words), a span is front matter
# — a title page, preface line, or table-of-contents entry — not a chapter, and
# it's dropped from the tree. Kept in sync with the analyzer's per-section filter.
MIN_SECTION_WORDS = 40


def chapters(text: str) -> list[tuple[str, str | None, str]]:
    """The real chapters as ``(section_id, title, body)``, ids ``ch1..chN``.

    Front matter (title page, preface, table-of-contents entries) is dropped by
    the word-count filter, and ids are assigned sequentially over what remains —
    so the ids are clean and are the *single source of truth* shared by
    ``build_structure`` and the analyzer's per-chapter arcs and world diffs.
    """
    kept = [
        (title, body)
        for title, body in segment.chapter_spans(text)
        if len(segment.words(body)) >= MIN_SECTION_WORDS
    ]
    return [(f"ch{i + 1}", title, body) for i, (title, body) in enumerate(kept)]


def build_structure(text: str) -> Section:
    """Deterministic structural tree for ``text``.

    One real chapter -> a flat single chapter Section; several -> a book.
    """
    chs = chapters(text)
    if len(chs) <= 1:
        title = chs[0][1] if chs else None
        return Section(id="ch1", level="chapter", title=title)
    return Section(
        id="book",
        level="book",
        title=None,
        children=[Section(id=cid, level="chapter", title=title) for cid, title, _body in chs],
    )


def leaves(section: Section) -> list[Section]:
    """Leaf sections (no children), in order."""
    if not section.children:
        return [section]
    out: list[Section] = []
    for child in section.children:
        out.extend(leaves(child))
    return out


def flat_beat_ids(section: Section) -> list[str]:
    """Every beat id under ``section``, depth-first, in order."""
    out = list(section.beat_ids)
    for child in section.children:
        out.extend(flat_beat_ids(child))
    return out


def covers(section: Section, beat_ids: list[str]) -> bool:
    """True if the section's beat_ids exactly cover ``beat_ids`` (as a set)."""
    return set(flat_beat_ids(section)) == set(beat_ids)
