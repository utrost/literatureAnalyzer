"""Fold per-chapter world observations into one global world (S1, book scale).

The chunked Lector emits a `WorldDiff` per chapter; `merge_world` coalesces an
ordered list of them into a single `WorldSeed`. Deterministic and offline — the
model does the reading, this does the bookkeeping, so the merge is fully tested.

Entity resolution is two-layered:

1. **By id (primary).** The Lector is handed the entities-so-far and told to
   reuse their ids for recurring characters, so the same person carries one id
   across chapters. Same id → merged.
2. **By normalized name (backstop).** If two chapters give the same character
   different ids but the same name, they're still merged — a deterministic guard
   against the model forgetting to reuse an id. Fuzzier coreference ("the old
   man" = "Silas") is the LLM's job via context, not attempted here.

Field-merge rules keep a book-length snapshot sensible: identity fields (name,
appearance, wants) come from first appearance; `emotional_state` takes the most
recent chapter (it evolves); secrets and `known_by` accumulate.
"""

from __future__ import annotations

import re

from .schemas import Character, ChekhovObject, Location, Secret, WorldDiff, WorldSeed


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _resolve_id(entity, by_id: dict, name_to_id: dict[str, str]) -> str | None:
    """Return the canonical id for ``entity``: its own id if seen, else a prior
    entity with the same normalized name, else None (new entity)."""
    if entity.id in by_id:
        return entity.id
    return name_to_id.get(_norm(entity.name))


def _merge_character(existing: Character, incoming: Character) -> Character:
    return existing.model_copy(
        update={
            # identity from first appearance; state follows the latest chapter
            "emotional_state": incoming.emotional_state or existing.emotional_state,
            "secret": existing.secret or incoming.secret,
        }
    )


def merge_world(diffs: list[WorldDiff]) -> WorldSeed:
    """Fold ordered per-chapter WorldDiffs into one global WorldSeed."""
    chars: dict[str, Character] = {}
    char_name_to_id: dict[str, str] = {}
    locs: dict[str, Location] = {}
    loc_name_to_id: dict[str, str] = {}
    objs: dict[str, ChekhovObject] = {}
    obj_name_to_id: dict[str, str] = {}
    secrets: dict[str, Secret] = {}
    protagonist_id: str | None = None

    for diff in diffs:
        for c in diff.characters:
            cid = _resolve_id(c, chars, char_name_to_id)
            if cid is None:
                chars[c.id] = c
                char_name_to_id[_norm(c.name)] = c.id
            else:
                chars[cid] = _merge_character(chars[cid], c)
        for loc in diff.locations:
            lid = _resolve_id(loc, locs, loc_name_to_id)
            if lid is None:
                locs[loc.id] = loc
                loc_name_to_id[_norm(loc.name)] = loc.id
        for o in diff.chekhov_objects:
            oid = _resolve_id(o, objs, obj_name_to_id)
            if oid is None:
                objs[o.id] = o
                obj_name_to_id[_norm(o.name)] = o.id
        for s in diff.secrets:
            if s.id in secrets:
                known = list(dict.fromkeys(secrets[s.id].known_by + s.known_by))
                secrets[s.id] = secrets[s.id].model_copy(update={"known_by": known})
            else:
                secrets[s.id] = s
        if protagonist_id is None and diff.protagonist_id:
            protagonist_id = diff.protagonist_id

    # Fallback protagonist: first character seen, so the field is always valid.
    if protagonist_id is None or protagonist_id not in chars:
        protagonist_id = next(iter(chars), "")

    return WorldSeed(
        characters=list(chars.values()),
        locations=list(locs.values()),
        chekhov_objects=list(objs.values()),
        secrets=list(secrets.values()),
        protagonist_id=protagonist_id,
    )


def entities_summary(diffs: list[WorldDiff]) -> str:
    """A compact 'entities so far' block to hand the next chapter's Lector, so it
    reuses ids for recurring characters (the primary resolution mechanism)."""
    world = merge_world(diffs) if diffs else None
    if world is None or not world.characters:
        return "(none yet)"
    return "\n".join(f"- {c.id}: {c.name}" for c in world.characters)
