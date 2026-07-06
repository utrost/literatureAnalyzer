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


def build_structure(text: str) -> Section:
    """Deterministic structural tree for ``text``.

    One span -> a single chapter Section (flat). Multiple spans -> a book whose
    children are the chapters, ids ``ch1..chN`` matching ``chapter_spans`` order.
    """
    spans = segment.chapter_spans(text)
    if len(spans) <= 1:
        title = spans[0][0] if spans else None
        return Section(id="ch1", level="chapter", title=title)
    chapters = [
        Section(id=f"ch{i + 1}", level="chapter", title=title)
        for i, (title, _body) in enumerate(spans)
    ]
    return Section(id="book", level="book", title=None, children=chapters)


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
