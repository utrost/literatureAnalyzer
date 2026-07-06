"""Pydantic schemas.

Two families live here:

1. **The shared contract** — Shape, StyleProfile, WorldSeed, BeatPlan and their
   parts. These are copied deliberately from Endless's ``story_engine/schemas.py``
   so that what this tool *produces* is exactly what Endless *consumes*. Analyze
   a story, hand the pieces to Endless, regenerate in the same shape and voice.
   Keep these in sync with Endless; drift breaks the contract.

2. **Analysis-specific types** — ArcSample, ShapeMatch, StyleEvidence,
   StoryAnalysis. These wrap the contract objects with the measurements and
   confidence that a *deconstruction* produces but a *generation* never needs.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ============================================================================
# Shared contract with Endless (do not let these drift)
# ============================================================================


# ---------- Shape (abstract arc) --------------------------------------------


class ShapeBeat(BaseModel):
    id: str
    valence: float = Field(ge=-1.0, le=1.0)
    function: str
    weight: float = Field(default=1.0, gt=0.0)


class Shape(BaseModel):
    name: str
    beats: list[ShapeBeat]


# ---------- Style -----------------------------------------------------------


class StyleAxes(BaseModel):
    sentence_length_mean: int
    sentence_length_variance: Literal["low", "medium", "high"]
    diction_register: Literal["formal", "colloquial", "archaic", "technical"]
    latinate_ratio: Literal["low", "medium", "high"]
    psychic_distance: Literal["far", "medium", "close"]
    show_tell_ratio: float = Field(ge=0.0, le=1.0)
    description_density: Literal["sparse", "medium", "lush"]
    dialogue_attribution: Literal["minimal", "conventional", "elaborate"]


class StyleProfile(BaseModel):
    id: str
    name: str
    axes: StyleAxes
    authored_brief: str
    exemplars: list[str] = Field(default_factory=list)


# ---------- World graph -----------------------------------------------------


class Character(BaseModel):
    id: str
    name: str
    appearance: str
    wants: str
    emotional_state: str
    secret: str | None = None


class Location(BaseModel):
    id: str
    name: str
    description: str


class ChekhovObject(BaseModel):
    id: str
    name: str
    description: str


class Secret(BaseModel):
    id: str
    content: str
    known_by: list[str] = Field(default_factory=list)


class WorldSeed(BaseModel):
    characters: list[Character]
    locations: list[Location]
    chekhov_objects: list[ChekhovObject] = Field(default_factory=list)
    secrets: list[Secret] = Field(default_factory=list)
    protagonist_id: str


# ---------- Beats -----------------------------------------------------------


class Beat(BaseModel):
    id: str
    shape_function: str
    target_words: int = Field(gt=0)
    pov: str
    required_events: list[str]
    forbidden_events: list[str] = Field(default_factory=list)
    mood: str
    rationale: str | None = None


class BeatPlan(BaseModel):
    beats: list[Beat]


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


class StoryAnalysis(BaseModel):
    """Top-level deconstruction of one story.

    ``style`` and ``shape`` are always present (deterministic passes). ``world``
    and ``beats`` are filled only by the LLM-powered ``--deep`` passes and are
    ``None`` otherwise.
    """

    source: str = Field(description="Where the text came from (path or label).")
    word_count: int
    style: StyleProfile
    style_evidence: StyleEvidence
    shape: ShapeMatch
    world: WorldSeed | None = None
    beats: BeatPlan | None = None


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


class Divergence(BaseModel):
    """How well a regeneration preserved a source story's structure.

    ``world`` and ``beats`` are present only when *both* compared analyses have
    them (i.e. both were run with ``--deep``). ``overall`` is the mean of the
    available per-dimension similarities.
    """

    source_a: str
    source_b: str
    shape: ShapeDivergence
    style: StyleDivergence
    world: WorldDivergence | None = None
    beats: BeatDivergence | None = None
    overall: float = Field(ge=0.0, le=1.0)
