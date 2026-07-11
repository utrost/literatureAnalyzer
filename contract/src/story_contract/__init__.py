"""The shared schema contract — the single source of truth.

These four types (and their parts) are what the Literature Analyzer *produces*
and Endless *consumes*: `Shape` (emotional arc), `StyleProfile` (narrator voice),
`WorldSeed` (world graph), `BeatPlan` (functional beats). Both tools import them
from here so the round-trip can't silently break — this package replaces the two
verbatim copies that used to live in each repo's `schemas.py`.

Kept intentionally tiny: pydantic only, no tool-specific logic, no LLM deps. The
analyzer's analysis-only types and Endless's generation-only types stay in their
own `schemas.py`, layered on top of these.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------- Shape (abstract arc) --------------------------------------------


class ShapeBeat(BaseModel):
    id: str
    valence: float = Field(ge=-1.0, le=1.0)
    function: str
    weight: float = Field(default=1.0, gt=0.0)


class Shape(BaseModel):
    name: str
    beats: list[ShapeBeat]
    children: list["Shape"] = Field(
        default_factory=list,
        description="Nested sub-arcs (S0, book scale): a book-arc's chapter-arcs. Empty = flat.",
    )


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
    model_config = {"populate_by_name": True}
    id: str
    name: str
    axes: StyleAxes
    authored_brief: str
    exemplars: list[str] = Field(default_factory=list)
    meta: dict | None = Field(default=None, alias="_meta")


# ---------- World graph -----------------------------------------------------


class Character(BaseModel):
    id: str
    name: str
    appearance: str
    wants: str
    emotional_state: str
    secret: str | None = None
    archetype: str | None = Field(default=None, description="Archetype matching this character (e.g. 'protagonist', 'mentor', 'shadow', 'herald', 'threshold_guardian', 'trickster', 'shapeshifter', 'ally')")


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
    model_config = {"populate_by_name": True}
    characters: list[Character]
    locations: list[Location]
    chekhov_objects: list[ChekhovObject] = Field(default_factory=list)
    secrets: list[Secret] = Field(default_factory=list)
    protagonist_id: str
    meta: dict | None = Field(default=None, alias="_meta")


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
    tropes: list[str] = Field(default_factory=list, description="Tropes present in this beat, from our taxonomy (e.g. 'faustian_bargain', 'noble_sacrifice')")


class Section(BaseModel):
    """A node in a story's structural hierarchy (S0 — book scale).

    A flat short story is a single ``chapter`` Section; a novel nests
    ``book → part → chapter → scene``. Leaf sections group beats by id
    (``beat_ids``). On a BeatPlan, ``structure=None`` means flat — one implicit
    chapter — which is exactly today's behavior.
    """

    id: str
    level: Literal["book", "part", "chapter", "scene"]
    title: str | None = None
    children: list["Section"] = Field(default_factory=list)
    beat_ids: list[str] = Field(
        default_factory=list, description="Beats grouped directly under this section (typically leaves)."
    )


class BeatPlan(BaseModel):
    model_config = {"populate_by_name": True}
    beats: list[Beat]
    structure: Section | None = Field(
        default=None, description="Optional hierarchy over the beats (S0). None = flat."
    )
    meta: dict | None = Field(default=None, alias="_meta")


Section.model_rebuild()
Shape.model_rebuild()


__all__ = [
    "ShapeBeat", "Shape", "StyleAxes", "StyleProfile",
    "Character", "Location", "ChekhovObject", "Secret", "WorldSeed",
    "Beat", "Section", "BeatPlan",
]
