"""Story-time event log (S1, book scale).

Derives an ordered `WorldEvent` history from the per-chapter `WorldDiff`s: who was
introduced, whose emotional state changed, who learned which secret, and *in which
chapter*. Deterministic and offline — the diffs already carry the observations;
this just records the deltas as story-time moves forward. A snapshot at any point
is the merge of the diffs up to that section (`snapshot_at`).

Entity resolution matches `worldmerge` (id first, normalized-name backstop) so the
log and the merged world agree on which mentions are the same entity.
"""

from __future__ import annotations

from . import worldmerge
from .schemas import WorldDiff, WorldEvent, WorldSeed


def build_event_log(diffs: list[WorldDiff]) -> list[WorldEvent]:
    events: list[WorldEvent] = []
    seq = 0

    char_state: dict[str, str] = {}
    char_name_to_id: dict[str, str] = {}
    seen_locs: dict[str, str] = {}
    seen_objs: dict[str, str] = {}
    secret_known: dict[str, set[str]] = {}

    def emit(section_id, kind, entity_kind, entity_id, note=None):
        nonlocal seq
        events.append(
            WorldEvent(seq=seq, section_id=section_id, kind=kind, entity_kind=entity_kind, entity_id=entity_id, note=note)
        )
        seq += 1

    for diff in diffs:
        sid = diff.section_id
        for c in diff.characters:
            key = worldmerge.norm_name(c.name)
            cid = c.id if c.id in char_state else char_name_to_id.get(key)
            if cid is None:
                char_name_to_id[key] = c.id
                char_state[c.id] = c.emotional_state
                emit(sid, "introduced", "character", c.id, note=c.name)
            elif c.emotional_state and c.emotional_state != char_state.get(cid):
                emit(sid, "state_changed", "character", cid, note=c.emotional_state)
                char_state[cid] = c.emotional_state
        for loc in diff.locations:
            key = worldmerge.norm_name(loc.name)
            if loc.id not in seen_locs and key not in seen_locs.values():
                seen_locs[loc.id] = key
                emit(sid, "introduced", "location", loc.id, note=loc.name)
        for o in diff.chekhov_objects:
            key = worldmerge.norm_name(o.name)
            if o.id not in seen_objs and key not in seen_objs.values():
                seen_objs[o.id] = key
                emit(sid, "introduced", "object", o.id, note=o.name)
        for s in diff.secrets:
            if s.id not in secret_known:
                secret_known[s.id] = set(s.known_by)
                emit(sid, "introduced", "secret", s.id, note=s.content)
            else:
                for knower in sorted(set(s.known_by) - secret_known[s.id]):
                    emit(sid, "secret_learned", "secret", s.id, note=knower)
                secret_known[s.id] |= set(s.known_by)

    return events


def snapshot_at(diffs: list[WorldDiff], through_section: str) -> WorldSeed:
    """Materialize the world as of the end of ``through_section`` (inclusive)."""
    upto: list[WorldDiff] = []
    for d in diffs:
        upto.append(d)
        if d.section_id == through_section:
            break
    return worldmerge.merge_world(upto)
