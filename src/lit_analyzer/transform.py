"""Transposition — retell a deconstructed story in a new setting and voice.

The capstone of the loop: take a `StoryAnalysis` (from `--deep`) and produce a
new one that keeps the story's *bones* and swaps its *surface*.

    KEEP  (held fixed, by construction)     SWAP  (transformed)
    ├─ Shape (emotional arc)                ├─ world surface  (names, appearance, setting)
    ├─ beat functions + order               ├─ beat events    (re-concretized in the setting)
    └─ wants · relationships · secrets      └─ narrator voice (substituted StyleProfile)

Control is layered from soft to hard (see `Transposition`): a setting brief and
free-text directives steer the model; explicit renames are enforced *in code*
after it returns, so a forced name is guaranteed regardless of what the model
does. The reskin must preserve every entity `id` (beats reference them) — that's
validated, not hoped for.

The LLM roles (`roles/reskinner.py`, `roles/beat_recaster.py`) are imported only
inside `transpose`, so this module stays import-clean without the deep extra.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .schemas import EntityMap, EntityMapping, StoryAnalysis, StyleProfile, WorldDiff, WorldSeed


class Transposition(BaseModel):
    """The control surface for a transposition."""

    setting: str = Field(description="Target-world brief, e.g. 'cyberpunk generation ship'.")
    directives: list[str] = Field(
        default_factory=list,
        description="Free-text steering honored literally: gender/age changes, relocations, tone.",
    )
    renames: dict[str, str] = Field(
        default_factory=dict,
        description="Entity id -> forced new name. Enforced deterministically after the model.",
    )
    style: StyleProfile | None = Field(
        default=None, description="Substitute narrator voice (e.g. one extracted from another author)."
    )


def parse_renames(items: list[str]) -> dict[str, str]:
    """Turn ['jim=N-7', 'tom=Tomasina'] into {'jim': 'N-7', 'tom': 'Tomasina'}."""
    out: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"bad --rename {item!r}; expected id=NewName")
        key, _, value = item.partition("=")
        key, value = key.strip(), value.strip()
        if not key or not value:
            raise ValueError(f"bad --rename {item!r}; expected id=NewName")
        out[key] = value
    return out


def spec_block(spec: Transposition) -> str:
    """The steering block appended to both transform prompts' user messages."""
    lines = [f"Target setting: {spec.setting}"]
    if spec.directives:
        lines.append("")
        lines.append("Directives (honor each one literally):")
        lines += [f"- {d}" for d in spec.directives]
    if spec.renames:
        lines.append("")
        lines.append("Forced names (use verbatim for these ids):")
        lines += [f"- {k} -> {v}" for k, v in spec.renames.items()]
    return "\n".join(lines)


def _apply_renames(world: WorldSeed, renames: dict[str, str]) -> WorldSeed:
    """Enforce forced names in code, so hard renames don't depend on the model."""
    if not renames:
        return world

    def rn(entity):
        return entity.model_copy(update={"name": renames[entity.id]}) if entity.id in renames else entity

    return world.model_copy(
        update={
            "characters": [rn(c) for c in world.characters],
            "locations": [rn(loc) for loc in world.locations],
            "chekhov_objects": [rn(o) for o in world.chekhov_objects],
        }
    )


def build_entity_map(original: WorldSeed, reskinned: WorldSeed) -> EntityMap:
    """The id → new-name table from a reskin: every entity, old and new name.

    Records all entities (not just changed ones) so the map is a complete,
    inspectable record of how the world was reskinned. Ids are preserved by
    ``transpose`` (validated), so aligning by id is exact.
    """
    orig = {e.id: e.name for grp in (original.characters, original.locations, original.chekhov_objects) for e in grp}
    mappings: list[EntityMapping] = []
    for kind, group in (
        ("character", reskinned.characters),
        ("location", reskinned.locations),
        ("object", reskinned.chekhov_objects),
    ):
        for e in group:
            mappings.append(
                EntityMapping(id=e.id, kind=kind, original_name=orig.get(e.id, e.name), new_name=e.name)
            )
    return EntityMap(mappings=mappings)


def apply_entity_map_to_diffs(diffs: list[WorldDiff], emap: EntityMap) -> list[WorldDiff]:
    """Rename every entity in every per-chapter diff by id, per the map.

    This is what makes a book-scale transposition consistent: the merged world
    and all per-chapter observations use the *same* new name for each id, so a
    character can't be reskinned one way in the merged world and another way in
    a chapter's diff.
    """
    def rn(entity):
        new = emap.name_for(entity.id)
        return entity.model_copy(update={"name": new}) if new is not None else entity

    return [
        diff.model_copy(
            update={
                "characters": [rn(c) for c in diff.characters],
                "locations": [rn(loc) for loc in diff.locations],
                "chekhov_objects": [rn(o) for o in diff.chekhov_objects],
            }
        )
        for diff in diffs
    ]


def _check_ids_preserved(original: list, transposed: list, kind: str) -> None:
    before = {e.id for e in original}
    after = {e.id for e in transposed}
    if before != after:
        raise ValueError(
            f"transpose changed {kind} ids ({before} -> {after}); the structure "
            "must be preserved so beats still reference the right entities."
        )


def transpose(cfg, analysis: StoryAnalysis, spec: Transposition) -> StoryAnalysis:
    """Transpose ``analysis`` into ``spec``'s setting and (optional) voice.

    ``cfg`` is a ``DeepConfig``. Requires the source analysis to carry world and
    beats (i.e. it was produced with ``--deep``).
    """
    if analysis.world is None or analysis.beats is None:
        raise ValueError(
            "transpose needs a world graph and beats — run the source analysis "
            "with --deep first."
        )

    from .roles import beat_recaster, reskinner  # deferred: only paid on a real run

    world = reskinner.reskin_world(cfg, world=analysis.world, spec=spec)
    _check_ids_preserved(analysis.world.characters, world.characters, "character")
    _check_ids_preserved(analysis.world.locations, world.locations, "location")
    world = _apply_renames(world, spec.renames)

    beats = beat_recaster.recast_beats(cfg, beats=analysis.beats, world=world, spec=spec)

    # S3: freeze the reskin as a persistent id → new-name map and apply it to
    # every per-chapter diff, so a book-scale transposition renames each entity
    # identically in the merged world and in every chapter.
    entity_map = build_entity_map(analysis.world, world)
    world_diffs = apply_entity_map_to_diffs(analysis.world_diffs, entity_map)

    return analysis.model_copy(
        update={
            "source": f"{analysis.source} → {spec.setting}",
            "world": world,
            "beats": beats,
            "style": spec.style or analysis.style,
            "world_diffs": world_diffs,
            "entity_map": entity_map,
        }
    )
