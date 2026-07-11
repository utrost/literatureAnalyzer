"""Pydantic schemas.

Two families live here:

1. **The shared contract** — Shape, StyleProfile, WorldSeed, BeatPlan and their
   parts. These now live in the standalone ``story_contract`` package (in
   ``../contract``) and are re-exported here, so what this tool *produces* is
   exactly what Endless *consumes* from the *same* definition — no more verbatim
   copies to keep in sync. Both repos import them from ``story_contract``.

2. **Analysis-specific types** — ArcSample, ShapeMatch, StyleEvidence,
   StoryAnalysis, and the S1/S3 additions. These wrap the contract objects with
   the measurements and confidence that a *deconstruction* produces but a
   *generation* never needs. They stay here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# The shared contract — single source of truth in the story_contract package.
from story_contract import (  # noqa: F401  (re-exported for existing importers)
    Beat,
    BeatPlan,
    Character,
    ChekhovObject,
    Location,
    Secret,
    Section,
    Shape,
    ShapeBeat,
    StyleAxes,
    StyleProfile,
    WorldSeed,
)


# ============================================================================
# Analysis-specific types (what deconstruction adds)
# ============================================================================


class ArcSample(BaseModel):
    """One sampled point on the story's emotional arc."""

    index: int = Field(ge=0)
    position: float = Field(ge=0.0, le=1.0, description="Fractional position through the text.")
    valence: float = Field(ge=-1.0, le=1.0, description="Normalized sentiment at this point.")


class ShapeScore(BaseModel):
    """How well one reference shape fits the measured arc. Lower distance = better."""

    shape: str
    distance: float = Field(ge=0.0)
    confidence: float = Field(ge=0.0, le=1.0)


class ShapeMatch(BaseModel):
    """The result of classifying a measured arc against the Reagan six."""

    best: str = Field(description="Name of the closest reference shape.")
    curve: list[ArcSample]
    ranking: list[ShapeScore] = Field(description="All shapes, best first.")


class SectionArc(BaseModel):
    """Multi-scale arc (S0): a ShapeMatch measured over one structural section."""

    section_id: str
    level: str
    title: str | None = None
    shape: ShapeMatch


class StyleEvidence(BaseModel):
    """Raw measurements the style axes were derived from. Debug / transparency."""

    sentence_count: int
    word_count: int
    sentence_length_mean: float
    sentence_length_stdev: float
    dialogue_word_ratio: float
    modifier_ratio: float
    latinate_ratio: float
    first_person_ratio: float


class StoryClassification(BaseModel):
    genre: list[str] = Field(default_factory=list, description="Primary genres, e.g. ['horror', 'mystery']")
    structural_template: str = Field(description="Plot framework name, e.g. 'three_act', 'heros_journey', 'save_the_cat', 'kishotenketsu'")
    notes: str | None = None


class WorldDiff(BaseModel):
    """Per-chapter world observation (S1, book scale).

    The entities seen or updated within one section. ``merge_world`` folds an
    ordered list of these into a single global ``WorldSeed``. This is a *diff*
    against the accumulating graph (new + updated entities), not yet a full
    op-based event log — story-time event-sourcing (adds/removes/field-ops) is
    the deferred refinement. The chunked Lector is told the entities-so-far so it
    reuses their ids, which is how recurring characters resolve across chapters.
    """

    section_id: str
    characters: list[Character] = Field(default_factory=list)
    locations: list[Location] = Field(default_factory=list)
    chekhov_objects: list[ChekhovObject] = Field(default_factory=list)
    secrets: list[Secret] = Field(default_factory=list)
    protagonist_id: str | None = None


class WorldEvent(BaseModel):
    """One entry in the story-time event log (S1, book scale).

    Derived deterministically from the ordered per-chapter ``WorldDiff``s: it
    records *when* something happened (which section) so the world is a history,
    not just a snapshot — "Mara learned the lens exists in chapter 4". Snapshots
    at any point are materialized by folding the diffs up to that section.
    """

    seq: int = Field(ge=0, description="Global order across the whole story.")
    section_id: str
    kind: Literal["introduced", "state_changed", "secret_learned"]
    entity_kind: Literal["character", "location", "object", "secret"]
    entity_id: str
    note: str | None = None


class EntityMapping(BaseModel):
    """One entity's rename under a transposition (S3): id + old → new name."""

    id: str
    kind: Literal["character", "location", "object"]
    original_name: str
    new_name: str


class EntityMap(BaseModel):
    """The global, stable id → new-name table from a transposition (S3).

    Built once from the reskinned merged world, then applied deterministically to
    the merged world *and* every per-chapter ``WorldDiff`` — so a character reskins
    identically in every chapter instead of the model renaming it differently
    chunk to chunk. Persisted on the transposed ``StoryAnalysis`` so the mapping
    is inspectable and reproducible.
    """

    mappings: list[EntityMapping] = Field(default_factory=list)

    def name_for(self, entity_id: str) -> str | None:
        for m in self.mappings:
            if m.id == entity_id:
                return m.new_name
        return None


class StoryAnalysis(BaseModel):
    """Top-level deconstruction of one story.

    ``style`` and ``shape`` are always present (deterministic passes). ``world``,
    ``beats`` and ``classification`` are filled only by the LLM-powered ``--deep`` passes and are
    ``None`` otherwise.
    """

    source: str = Field(description="Where the text came from (path or label).")
    word_count: int
    style: StyleProfile
    style_evidence: StyleEvidence
    shape: ShapeMatch
    world: WorldSeed | None = None
    beats: BeatPlan | None = None
    classification: StoryClassification | None = None
    # S0 (book scale): deterministic structural hierarchy + per-section arcs.
    # A flat short story: structure is a single chapter, section_arcs is empty.
    structure: Section | None = None
    section_arcs: list[SectionArc] = Field(default_factory=list)
    # S1 (book scale): per-chapter world observations behind the merged `world`,
    # and the story-time event log derived from them. Empty for whole-text extraction.
    world_diffs: list[WorldDiff] = Field(default_factory=list)
    world_events: list[WorldEvent] = Field(default_factory=list)
    # S3 (transposition): the global id → new-name table, present only on a
    # transposed analysis. Applied identically across world + world_diffs.
    entity_map: EntityMap | None = None


# ---------- Divergence (the fidelity critic, §8.5) --------------------------
#
# The result of comparing two StoryAnalysis objects — typically an original and
# a regeneration. This compares *structures*, not texts: regeneration is meant
# to reword, so a low distance means the bones survived, not the sentences.
# Every sub-score is a similarity in [0, 1] where 1 means identical structure.


class AxisDelta(BaseModel):
    """One style axis compared across two analyses."""

    axis: str
    a: str
    b: str
    distance: float = Field(ge=0.0, le=1.0)


class ShapeDivergence(BaseModel):
    best_a: str
    best_b: str
    same_best: bool
    curve_distance: float = Field(ge=0.0, description="z-scored RMSE between the two arcs.")
    similarity: float = Field(ge=0.0, le=1.0)


class StyleDivergence(BaseModel):
    distance: float = Field(ge=0.0, le=1.0)
    similarity: float = Field(ge=0.0, le=1.0)
    axes: list[AxisDelta]


class WorldDivergence(BaseModel):
    characters_a: int
    characters_b: int
    character_overlap: float = Field(ge=0.0, le=1.0, description="Jaccard over character names.")
    protagonist_match: bool
    location_overlap: float = Field(ge=0.0, le=1.0)
    similarity: float = Field(ge=0.0, le=1.0)


class BeatDivergence(BaseModel):
    count_a: int
    count_b: int
    id_overlap: float = Field(ge=0.0, le=1.0, description="Jaccard over beat ids.")
    similarity: float = Field(ge=0.0, le=1.0)


class SectionArcPair(BaseModel):
    """One aligned chapter, compared across two analyses (S3).

    Carries the chapter's arc fidelity (``similarity``) and — when both sides
    grouped beats under chapters — the beat count on each side plus their
    agreement (``beat_similarity``), so pacing drift localizes per chapter.
    """

    index: int = Field(ge=0, description="Reading-order position the two chapters were aligned at.")
    title_a: str | None = None
    title_b: str | None = None
    best_a: str
    best_b: str
    same_best: bool
    curve_distance: float = Field(ge=0.0, description="z-scored RMSE between the two chapter arcs.")
    similarity: float = Field(ge=0.0, le=1.0, description="Per-chapter arc fidelity.")
    beats_a: int | None = None
    beats_b: int | None = None
    beat_similarity: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Per-chapter beat-count agreement (pacing)."
    )


class HierarchyDivergence(BaseModel):
    """Per-level (per-chapter) fidelity (S3, book scale).

    Whole-text `shape` says the books rise-and-fall alike; this says whether they
    do so *chapter by chapter*. Chapters are aligned by reading order; a count
    mismatch is penalized via ``alignment`` (unaligned chapters score zero).
    ``beat_similarity`` is present only when both analyses group beats under
    chapters — it measures per-chapter pacing, distinct from the arc shape.
    """

    count_a: int
    count_b: int
    alignment: float = Field(ge=0.0, le=1.0, description="Chapter-count agreement; 1.0 = equal counts.")
    pairs: list[SectionArcPair] = Field(default_factory=list)
    similarity: float = Field(
        ge=0.0, le=1.0,
        description="Mean per-chapter arc similarity, scaled by alignment. DIAGNOSTIC "
        "only — excluded from Divergence.overall because a per-chapter sentiment "
        "curve is reword-sensitive and faithful regeneration rewords by design.",
    )
    beat_similarity: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description="Mean per-chapter beat-count agreement (reword-robust pacing), scaled "
        "by alignment. This is the hierarchy's contribution to overall.",
    )


class Divergence(BaseModel):
    """How well a regeneration preserved a source story's structure.

    ``world`` and ``beats`` are present only when *both* compared analyses have
    them (i.e. both were run with ``--deep``). ``hierarchy`` is present only when
    both are chaptered (both carry ``section_arcs``). ``overall`` is the mean of
    the available per-dimension similarities.
    """

    source_a: str
    source_b: str
    shape: ShapeDivergence
    style: StyleDivergence
    world: WorldDivergence | None = None
    beats: BeatDivergence | None = None
    hierarchy: HierarchyDivergence | None = None
    overall: float = Field(ge=0.0, le=1.0)
