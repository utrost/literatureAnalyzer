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
    HierarchyDivergence,
    SectionArc,
    SectionArcPair,
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


def _arc_distance_similarity(a: ShapeMatch, b: ShapeMatch) -> tuple[bool, float, float]:
    """(same_best, curve_distance, similarity) for two arcs.

    Similarity is half credit for matching the named shape, half for arc-curve
    closeness — so a `cinderella` vs `man_in_hole` round-trip (both rise-and-fall)
    still scores well on the curve half instead of failing a binary match.
    """
    ca = [s.valence for s in a.curve]
    cb = [s.valence for s in b.curve]
    n = min(len(ca), len(cb)) or 1
    dist = arc._distance(
        arc._zscore(arc._resample(ca, n)), arc._zscore(arc._resample(cb, n))
    )
    same = a.best == b.best
    similarity = 0.5 * (1.0 if same else 0.0) + 0.5 * (1.0 / (1.0 + dist))
    return same, dist, similarity


def _shape_divergence(a: ShapeMatch, b: ShapeMatch) -> ShapeDivergence:
    same, dist, similarity = _arc_distance_similarity(a, b)
    return ShapeDivergence(
        best_a=a.best,
        best_b=b.best,
        same_best=same,
        curve_distance=round(dist, 4),
        similarity=round(similarity, 4),
    )


def _count_agreement(a: int, b: int) -> float:
    """1.0 when equal, decaying with the relative gap. Symmetric."""
    return 1.0 - abs(a - b) / max(a, b, 1)


def _beats_per_chapter(analysis) -> list[int] | None:
    """Beat count under each chapter section, in reading order — or None.

    None when the analysis isn't chaptered with beats grouped (a flat story, or
    a structure whose leaves don't carry beat_ids). Reads the structure tree, so
    it reflects how the analyzer actually grouped beats, not a re-derivation.
    """
    if analysis.structure is None or analysis.beats is None:
        return None
    chapters = [s for s in _walk_chapters(analysis.structure)]
    if not chapters:
        return None
    counts = [len(sec.beat_ids) for sec in chapters]
    return counts if any(counts) else None


def _walk_chapters(section):
    if section.level == "chapter":
        yield section
        return
    for child in section.children:
        yield from _walk_chapters(child)


def _hierarchy_divergence(a, b) -> HierarchyDivergence:
    """Per-chapter fidelity — arc shape and (when available) beat pacing.

    Chapters align by reading order. A count mismatch is penalized: only
    ``min(len_a, len_b)`` chapters align, and every mean is scaled by
    ``alignment`` so extra/missing chapters can't hide behind aligned ones.
    """
    arcs_a, arcs_b = a.section_arcs, b.section_arcs
    ca, cb = len(arcs_a), len(arcs_b)
    alignment = _count_agreement(ca, cb)

    beats_a = _beats_per_chapter(a)
    beats_b = _beats_per_chapter(b)
    have_beats = beats_a is not None and beats_b is not None

    pairs: list[SectionArcPair] = []
    for i in range(min(ca, cb)):
        sa, sb = arcs_a[i], arcs_b[i]
        same, dist, sim = _arc_distance_similarity(sa.shape, sb.shape)
        ba = beats_a[i] if have_beats and i < len(beats_a) else None
        bb = beats_b[i] if have_beats and i < len(beats_b) else None
        beat_sim = round(_count_agreement(ba, bb), 4) if ba is not None and bb is not None else None
        pairs.append(
            SectionArcPair(
                index=i,
                title_a=sa.title,
                title_b=sb.title,
                best_a=sa.shape.best,
                best_b=sb.shape.best,
                same_best=same,
                curve_distance=round(dist, 4),
                similarity=round(sim, 4),
                beats_a=ba,
                beats_b=bb,
                beat_similarity=beat_sim,
            )
        )

    mean_arc = _mean([p.similarity for p in pairs])
    beat_sims = [p.beat_similarity for p in pairs if p.beat_similarity is not None]
    beat_similarity = round(_mean(beat_sims) * alignment, 4) if beat_sims else None
    return HierarchyDivergence(
        count_a=ca,
        count_b=cb,
        alignment=round(alignment, 4),
        pairs=pairs,
        similarity=round(mean_arc * alignment, 4),
        beat_similarity=beat_similarity,
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

    # Directional containment (recall): do all original elements (b) exist in the candidate (a)?
    # Fleshing out or adding extra backstory elements should not penalize the score.
    char_overlap = len(names_a & names_b) / len(names_b) if names_b else 1.0
    loc_overlap = len(locs_a & locs_b) / len(locs_b) if locs_b else 1.0
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
    # Hierarchy only when both are chaptered (a flat story has no section_arcs).
    hierarchy = (
        _hierarchy_divergence(a, b)
        if a.section_arcs and b.section_arcs
        else None
    )

    sims = [shape.similarity, style.similarity]
    if world is not None:
        sims.append(world.similarity)
    if beats is not None:
        sims.append(beats.similarity)
    if hierarchy is not None:
        # Per-chapter *pacing* (beat counts) is reword-robust, so it counts toward
        # overall. Per-chapter *arc* similarity is deliberately excluded: a chapter
        # window is ~1/12 of a chapter, so its VADER curve is dominated by word
        # choice — a faithful regeneration (which rewords by design) drifts the
        # per-chapter arc even when the structure holds. It stays a diagnostic in
        # the report (localizing where arcs move), not a headline penalty for
        # rewording. The whole-text `shape` already scores arc fidelity robustly.
        if hierarchy.beat_similarity is not None:
            sims.append(hierarchy.beat_similarity)

    return Divergence(
        source_a=a.source,
        source_b=b.source,
        shape=shape,
        style=style,
        world=world,
        beats=beats,
        hierarchy=hierarchy,
        overall=round(_mean(sims), 4),
    )
