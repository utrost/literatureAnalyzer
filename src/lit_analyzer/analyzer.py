"""Analysis spine — the deterministic mirror of Endless's orchestrator.

``analyze`` always runs the two deterministic passes (arc classification, prose
metrics). When ``deep`` is set and a model is configured, it also runs the
LLM-powered Lector (world graph) and beat labeler. Nothing here calls a model
directly — the roles do — so this module imports cleanly with no LLM deps.
"""

from __future__ import annotations

from . import arc, metrics
from .schemas import BeatPlan, StoryAnalysis, WorldSeed, StoryClassification


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

    analysis = StoryAnalysis(
        source=source,
        word_count=evidence.word_count,
        style=style,
        style_evidence=evidence,
        shape=shape,
    )

    if world is not None:
        analysis.world = world
    elif deep_config is not None:
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
