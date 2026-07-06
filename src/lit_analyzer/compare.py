"""The fidelity critic — compare two deconstructions (design doc §8.5).

``compare(a, b)`` diffs two ``StoryAnalysis`` objects (typically an original and
a regeneration) and returns a ``Divergence``: per-dimension similarities plus an
overall score in [0, 1], where 1 means the structure was preserved.

Deterministic and offline — it operates on already-extracted structure, not on
prose or a model. It compares *bones, not words*: regeneration is supposed to
reword, so this deliberately never looks at the text. Quality judgment ("is the
new story any good?") is a different faculty and lives in Endless's eval harness,
not here.
"""

from __future__ import annotations

from . import arc
from .schemas import (
    AxisDelta,
    BeatDivergence,
    BeatPlan,
    Divergence,
    ShapeDivergence,
    ShapeMatch,
    StyleDivergence,
    StyleProfile,
    WorldDivergence,
    WorldSeed,
)

# Ordinal axes: distance is the gap between positions, normalized to [0, 1].
_ORDINAL: dict[str, list[str]] = {
    "sentence_length_variance": ["low", "medium", "high"],
    "latinate_ratio": ["low", "medium", "high"],
    "psychic_distance": ["far", "medium", "close"],
    "description_density": ["sparse", "medium", "lush"],
    "dialogue_attribution": ["minimal", "conventional", "elaborate"],
}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 1.0


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _shape_divergence(a: ShapeMatch, b: ShapeMatch) -> ShapeDivergence:
    ca = [s.valence for s in a.curve]
    cb = [s.valence for s in b.curve]
    n = min(len(ca), len(cb)) or 1
    dist = arc._distance(
        arc._zscore(arc._resample(ca, n)), arc._zscore(arc._resample(cb, n))
    )
    same = a.best == b.best
    # half credit for matching the named shape, half for arc-curve closeness
    similarity = 0.5 * (1.0 if same else 0.0) + 0.5 * (1.0 / (1.0 + dist))
    return ShapeDivergence(
        best_a=a.best,
        best_b=b.best,
        same_best=same,
        curve_distance=round(dist, 4),
        similarity=round(similarity, 4),
    )


def _style_divergence(a: StyleProfile, b: StyleProfile) -> StyleDivergence:
    ax_a, ax_b = a.axes, b.axes
    deltas: list[AxisDelta] = []

    # sentence_length_mean — relative numeric distance
    ma, mb = ax_a.sentence_length_mean, ax_b.sentence_length_mean
    deltas.append(
        AxisDelta(
            axis="sentence_length_mean",
            a=str(ma),
            b=str(mb),
            distance=round(min(1.0, abs(ma - mb) / max(ma, mb, 1)), 4),
        )
    )
    # show_tell_ratio — already in [0, 1]
    sa, sb = ax_a.show_tell_ratio, ax_b.show_tell_ratio
    deltas.append(
        AxisDelta(axis="show_tell_ratio", a=str(sa), b=str(sb), distance=round(abs(sa - sb), 4))
    )
    # ordinal axes
    for axis, order in _ORDINAL.items():
        va, vb = getattr(ax_a, axis), getattr(ax_b, axis)
        d = abs(order.index(va) - order.index(vb)) / (len(order) - 1)
        deltas.append(AxisDelta(axis=axis, a=va, b=vb, distance=round(d, 4)))
    # diction_register — nominal, match or not
    da, db = ax_a.diction_register, ax_b.diction_register
    deltas.append(AxisDelta(axis="diction_register", a=da, b=db, distance=0.0 if da == db else 1.0))

    dist = _mean([d.distance for d in deltas])
    return StyleDivergence(distance=round(dist, 4), similarity=round(1.0 - dist, 4), axes=deltas)


def _world_divergence(a: WorldSeed, b: WorldSeed) -> WorldDivergence:
    names_a = {c.name.lower() for c in a.characters}
    names_b = {c.name.lower() for c in b.characters}
    locs_a = {loc.name.lower() for loc in a.locations}
    locs_b = {loc.name.lower() for loc in b.locations}

    prot_a = next((c.name.lower() for c in a.characters if c.id == a.protagonist_id), None)
    prot_b = next((c.name.lower() for c in b.characters if c.id == b.protagonist_id), None)
    prot_match = prot_a is not None and prot_a == prot_b

    char_overlap = _jaccard(names_a, names_b)
    loc_overlap = _jaccard(locs_a, locs_b)
    similarity = _mean([char_overlap, loc_overlap, 1.0 if prot_match else 0.0])
    return WorldDivergence(
        characters_a=len(a.characters),
        characters_b=len(b.characters),
        character_overlap=round(char_overlap, 4),
        protagonist_match=prot_match,
        location_overlap=round(loc_overlap, 4),
        similarity=round(similarity, 4),
    )


def _beat_divergence(a: BeatPlan, b: BeatPlan) -> BeatDivergence:
    ids_a = {beat.id for beat in a.beats}
    ids_b = {beat.id for beat in b.beats}
    ca, cb = len(a.beats), len(b.beats)
    count_sim = 1.0 - abs(ca - cb) / max(ca, cb, 1)
    id_overlap = _jaccard(ids_a, ids_b)
    return BeatDivergence(
        count_a=ca,
        count_b=cb,
        id_overlap=round(id_overlap, 4),
        similarity=round(_mean([count_sim, id_overlap]), 4),
    )


def compare(a, b) -> Divergence:
    """Compare two StoryAnalysis objects into a Divergence.

    ``world`` and ``beats`` are compared only when *both* analyses carry them
    (both were run with ``--deep``); otherwise those sub-scores are ``None`` and
    don't count toward ``overall``.
    """
    shape = _shape_divergence(a.shape, b.shape)
    style = _style_divergence(a.style, b.style)
    world = _world_divergence(a.world, b.world) if a.world and b.world else None
    beats = _beat_divergence(a.beats, b.beats) if a.beats and b.beats else None

    sims = [shape.similarity, style.similarity]
    if world is not None:
        sims.append(world.similarity)
    if beats is not None:
        sims.append(beats.similarity)

    return Divergence(
        source_a=a.source,
        source_b=b.source,
        shape=shape,
        style=style,
        world=world,
        beats=beats,
        overall=round(_mean(sims), 4),
    )
