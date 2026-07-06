"""Analysis spine — the deterministic mirror of Endless's orchestrator.

``analyze`` always runs the two deterministic passes (arc classification, prose
metrics). When ``deep`` is set and a model is configured, it also runs the
LLM-powered Lector (world graph) and beat labeler. Nothing here calls a model
directly — the roles do — so this module imports cleanly with no LLM deps.
"""

from __future__ import annotations

from . import arc, metrics, segment, structure
from .schemas import (
    BeatPlan,
    SectionArc,
    StoryAnalysis,
    StoryClassification,
    WorldSeed,
)

# Chapters shorter than this (words) aren't given their own arc — too little
# signal to sample. They still appear in the structure tree.
_MIN_SECTION_WORDS = 40


def analyze(
    text: str,
    *,
    source: str = "text",
    segments: int = arc.DEFAULT_SEGMENTS,
    deep_config: "object | None" = None,
    world: WorldSeed | None = None,
    beats: BeatPlan | None = None,
    classification: StoryClassification | None = None,
) -> StoryAnalysis:
    """Deconstruct ``text`` into a StoryAnalysis.

    The deterministic passes (arc, metrics) always run. The world graph,
    beats, and classification are filled in one of three ways, checked in order:

    1. A supplied ``world`` / ``beats`` / ``classification`` wins outright — this is the hook the
       store uses to inject cached artifacts, and that a user uses to inject a
       hand-edited ``world.json`` (modify-then-reuse). No model is called.
    2. Otherwise, if ``deep_config`` is set, the LLM roles compute them. The
       role imports are deferred so the deterministic path needs no LLM deps.
    3. Otherwise they stay ``None``.
    """
    style, evidence = metrics.measure(text)
    shape = arc.classify(text, segments=segments)

    # S0: deterministic structural hierarchy + per-chapter (multi-scale) arcs.
    # A markerless short story -> a single chapter and no per-section arcs.
    story_structure = structure.build_structure(text)
    section_arcs = _section_arcs(text, segments=segments)

    analysis = StoryAnalysis(
        source=source,
        word_count=evidence.word_count,
        style=style,
        style_evidence=evidence,
        shape=shape,
        structure=story_structure,
        section_arcs=section_arcs,
    )

    if world is not None:
        analysis.world = world
    elif deep_config is not None:
        if _is_chaptered(story_structure):
            # S1: chunked per-chapter extraction, merged into one world.
            diffs = _chunked_world_diffs(deep_config, text)
            from . import worldlog, worldmerge

            analysis.world = worldmerge.merge_world(diffs)
            analysis.world_diffs = diffs
            analysis.world_events = worldlog.build_event_log(diffs)
        else:
            from .roles import lector  # deferred: only paid on a real deep call

            analysis.world = lector.extract_world(deep_config, text=text)

    if beats is not None:
        analysis.beats = beats
    elif deep_config is not None:
        from .roles import beat_labeler  # deferred

        analysis.beats = beat_labeler.label_beats(deep_config, text=text, shape=shape.best)

    if classification is not None:
        analysis.classification = classification
    elif deep_config is not None:
        from .roles import classifier  # deferred

        analysis.classification = classifier.classify_story(deep_config, text=text)

    return analysis


def _is_chaptered(story_structure) -> bool:
    """True when the deterministic structure found more than one chapter."""
    return story_structure is not None and story_structure.level == "book"


def _chunked_world_diffs(deep_config, text: str):
    """Run the chunked Lector chapter-by-chapter, feeding entities-so-far forward
    so recurring characters keep their ids. Returns the ordered WorldDiffs."""
    from . import worldmerge
    from .roles import chunked_lector

    diffs = []
    for i, (_title, body) in enumerate(segment.chapter_spans(text)):
        if len(segment.words(body)) < _MIN_SECTION_WORDS:
            continue
        diff = chunked_lector.extract_chapter(
            deep_config,
            section_id=f"ch{i + 1}",
            text=body,
            entities_so_far=worldmerge.entities_summary(diffs),
        )
        diffs.append(diff)
    return diffs


def _section_arcs(text: str, *, segments: int) -> list[SectionArc]:
    """A ShapeMatch per chapter, for a chaptered text. Empty for a flat story."""
    spans = segment.chapter_spans(text)
    if len(spans) <= 1:
        return []
    arcs: list[SectionArc] = []
    for i, (title, body) in enumerate(spans):
        if len(segment.words(body)) < _MIN_SECTION_WORDS:
            continue
        arcs.append(
            SectionArc(
                section_id=f"ch{i + 1}",
                level="chapter",
                title=title,
                shape=arc.classify(body, segments=segments),
            )
        )
    return arcs
