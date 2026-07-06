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

from .schemas import StoryAnalysis, StyleProfile, WorldSeed


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

    return analysis.model_copy(
        update={
            "source": f"{analysis.source} → {spec.setting}",
            "world": world,
            "beats": beats,
            "style": spec.style or analysis.style,
        }
    )
