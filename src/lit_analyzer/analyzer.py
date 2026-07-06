"""Analysis spine — the deterministic mirror of Endless's orchestrator.

``analyze`` always runs the two deterministic passes (arc classification, prose
metrics). When ``deep`` is set and a model is configured, it also runs the
LLM-powered Lector (world graph) and beat labeler. Nothing here calls a model
directly — the roles do — so this module imports cleanly with no LLM deps.
"""

from __future__ import annotations

from . import arc, metrics
from .schemas import StoryAnalysis


def analyze(
    text: str,
    *,
    source: str = "text",
    segments: int = arc.DEFAULT_SEGMENTS,
    deep_config: "object | None" = None,
) -> StoryAnalysis:
    """Deconstruct ``text`` into a StoryAnalysis.

    ``deep_config`` is a ``DeepConfig`` (from ``config``) or ``None``. When
    provided, the LLM roles run to fill ``world`` and ``beats``; the import of
    those roles is deferred so the deterministic path never needs LLM deps.
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

    if deep_config is not None:
        # Deferred import: only paid when --deep is actually used.
        from .roles import beat_labeler, lector

        analysis.world = lector.extract_world(deep_config, text=text)
        analysis.beats = beat_labeler.label_beats(
            deep_config, text=text, shape=shape.best
        )

    return analysis
