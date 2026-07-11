"""Headless edit core — apply typed edits to a deconstruction, validate, re-emit.

This is the engine a Story Workbench GUI would draw forms over (see
`BOOK_SCALE_ROADMAP.md`): load a `StoryAnalysis`, mutate contract fields by
path, re-validate against the schema, and hand the result to
`bridge.emit_endless(_doc)`. Deterministic, no model.

The discipline that keeps the round-trip working: edits land in the **structured**
artifacts (world / beats / style / shape), never in prose. This module edits the
schema instance and re-validates it; it never parses natural language back into
types.

Paths are dotted. Lists whose elements carry an `id` are indexed by that id, so
a character or beat is addressed by name of its id, not position:

    world.protagonist_id=silas
    world.characters.silas.wants=to escape the tithe
    world.characters.silas.emotional_state=hunted
    beats.ch2_fall.required_events=Silas confronts Kael|the light fails   # '|' → list
    shape.best=tragedy
    style.axes.psychic_distance=close
"""

from __future__ import annotations

from pydantic import ValidationError

from .schemas import StoryAnalysis


class EditError(ValueError):
    """A bad edit path, value, or a mutation that fails schema validation."""


def parse_edit(spec: str) -> tuple[str, str]:
    """'path=value' → (path, value). Value may contain '='; only the first splits."""
    if "=" not in spec:
        raise EditError(f"bad --set {spec!r}; expected path=value")
    path, _, value = spec.partition("=")
    path = path.strip()
    if not path:
        raise EditError(f"bad --set {spec!r}; empty path")
    return path, value.strip()


def _coerce(existing, raw: str):
    """Coerce the raw string to the shape of the field's current value."""
    if isinstance(existing, bool):
        return raw.strip().lower() in {"true", "1", "yes", "on"}
    if isinstance(existing, list):
        return [s.strip() for s in raw.split("|") if s.strip()]
    if isinstance(existing, int):  # bool handled above
        return int(raw)
    if isinstance(existing, float):
        return float(raw)
    return raw  # str, or None (optional field) → treat as text


def _normalize_segments(path: str) -> list[str]:
    """Split a path, with a friendly alias so `beats.<id>` addresses the list.

    `beats` on a StoryAnalysis is a BeatPlan whose beat list lives at `.beats`,
    so the literal path is `beats.beats.<id>`. Users think of `beats` as the
    list, so `beats.<id>.<field>` is rewritten to `beats.beats.<id>.<field>`.
    The explicit `beats.beats…`, and `beats.structure…`, still work unchanged.
    """
    segs = path.split(".")
    if len(segs) > 1 and segs[0] == "beats" and segs[1] not in {"beats", "structure", "meta"}:
        segs.insert(1, "beats")
    return segs


def _navigate(data: dict, path: str) -> tuple[dict, str]:
    """Walk ``path`` to (parent_dict, final_field). Lists are indexed by element id."""
    segments = _normalize_segments(path)
    cur = data
    for seg in segments[:-1]:
        if isinstance(cur, dict):
            if seg not in cur:
                raise EditError(f"no field {seg!r} in path {path!r}")
            cur = cur[seg]
        elif isinstance(cur, list):
            match = next((x for x in cur if isinstance(x, dict) and x.get("id") == seg), None)
            if match is None:
                raise EditError(f"no item with id {seg!r} in path {path!r}")
            cur = match
        else:
            raise EditError(f"cannot descend into {seg!r} in path {path!r}")
    final = segments[-1]
    if not isinstance(cur, dict) or final not in cur:
        raise EditError(f"unknown field {final!r} in path {path!r}")
    return cur, final


def apply_edits(analysis: StoryAnalysis, specs: list[str]) -> StoryAnalysis:
    """Apply ``path=value`` edits to ``analysis`` and re-validate the result.

    Returns a new, schema-valid ``StoryAnalysis``. Raises ``EditError`` on a bad
    path or a mutation that violates the schema (e.g. a wrong type).
    """
    if not specs:
        return analysis
    data = analysis.model_dump()
    for spec in specs:
        path, raw = parse_edit(spec)
        parent, final = _navigate(data, path)
        parent[final] = _coerce(parent[final], raw)
    try:
        return StoryAnalysis.model_validate(data)
    except ValidationError as exc:
        raise EditError(f"edit produced an invalid analysis: {exc}") from exc


def validate_contract(analysis: StoryAnalysis) -> list[str]:
    """Contract invariants a regeneration relies on. Empty list = clean.

    Advisory (the Workbench surfaces these); schema validity is already enforced
    by ``apply_edits``. These are the cross-field rules pydantic can't express.
    """
    issues: list[str] = []
    world = analysis.world
    if world is not None:
        char_ids = [c.id for c in world.characters]
        for kind, ids in (
            ("character", char_ids),
            ("location", [l.id for l in world.locations]),
            ("object", [o.id for o in world.chekhov_objects]),
        ):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            if dupes:
                issues.append(f"duplicate {kind} id(s): {', '.join(dupes)}")
        if world.protagonist_id not in char_ids:
            issues.append(f"protagonist_id {world.protagonist_id!r} is not a character id")
        for s in world.secrets:
            unknown = [k for k in s.known_by if k not in char_ids]
            if unknown:
                issues.append(f"secret {s.id!r} known_by references non-characters: {', '.join(unknown)}")

    beats = analysis.beats
    if beats is not None:
        bids = [b.id for b in beats.beats]
        dupes = sorted({i for i in bids if bids.count(i) > 1})
        if dupes:
            issues.append(f"duplicate beat id(s): {', '.join(dupes)}")
        if analysis.structure is not None:
            known = set(bids)
            for missing in sorted(_structure_beat_ids(analysis.structure) - known):
                issues.append(f"structure references unknown beat id {missing!r}")
    return issues


def _structure_beat_ids(section) -> set[str]:
    ids = set(section.beat_ids)
    for child in section.children:
        ids |= _structure_beat_ids(child)
    return ids
