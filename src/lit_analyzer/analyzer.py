"""Analysis spine — the deterministic mirror of Endless's orchestrator.

``analyze`` always runs the two deterministic passes (arc classification, prose
metrics). When ``deep`` is set and a model is configured, it also runs the
LLM-powered Lector (world graph) and beat labeler. Nothing here calls a model
directly — the roles do — so this module imports cleanly with no LLM deps.
"""

from __future__ import annotations

from . import arc, metrics, structure
from .schemas import (
    BeatPlan,
    SectionArc,
    StoryAnalysis,
    StoryClassification,
    WorldSeed,
)


def analyze(
    text: str,
    *,
    source: str = "text",
    segments: int = arc.DEFAULT_SEGMENTS,
    deep_config: "object | None" = None,
    world: WorldSeed | None = None,
    beats: BeatPlan | None = None,
    classification: StoryClassification | None = None,
    chunk_cache: "object | None" = None,
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
            diffs = _chunked_world_diffs(deep_config, text, chunk_cache)
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
        if _is_chaptered(story_structure):
            # S1 bridge: label beats per chapter and nest them under the
            # structure (populate Section.beat_ids) -> a hierarchical BeatPlan.
            analysis.beats = _hierarchical_beats(deep_config, text, section_arcs)
        else:
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


def _hierarchical_beats(deep_config, text: str, section_arcs) -> BeatPlan:
    """Label beats per chapter and assemble a hierarchical BeatPlan (S1 bridge).

    Each chapter is labeled against its own (multi-scale) arc; its beat ids are
    namespaced by the section (``ch1_eq``) so they stay unique across the book.
    The flat ``beats`` list (all chapters, reading order) is what existing
    consumers use; ``structure`` groups them by populating each chapter's
    ``beat_ids``. Endless still iterates the flat list; the hierarchy is there
    for book-scale generation and round-trip comparison.
    """
    from .schemas import BeatPlan, Section
    from .roles import beat_labeler

    shape_by_section = {sa.section_id: sa.shape.best for sa in section_arcs}
    flat: list = []
    chapters: list[Section] = []
    for section_id, title, body in structure.chapters(text):
        plan = beat_labeler.label_beats(
            deep_config, text=body, shape=shape_by_section.get(section_id, "man_in_hole")
        )
        beat_ids: list[str] = []
        for b in plan.beats:
            nb = b.model_copy(update={"id": f"{section_id}_{b.id}"})
            flat.append(nb)
            beat_ids.append(nb.id)
        chapters.append(Section(id=section_id, level="chapter", title=title, beat_ids=beat_ids))
    return BeatPlan(beats=flat, structure=Section(id="book", level="book", children=chapters))


def _chunked_world_diffs(deep_config, text: str, chunk_cache=None):
    """Run the chunked Lector chapter-by-chapter, feeding entities-so-far forward
    so recurring characters keep their ids. Returns the ordered WorldDiffs.

    With a ``chunk_cache``, unchanged chapters (same text + same entities-so-far)
    are reused instead of re-calling the model — the incremental cache (S1).
    """
    from . import worldmerge
    from .roles import chunked_lector

    diffs = []
    for section_id, _title, body in structure.chapters(text):
        entities = worldmerge.entities_summary(diffs)

        cached = None
        key = None
        if chunk_cache is not None:
            from .chunkcache import chapter_key

            key = chapter_key(body, entities)
            cached = chunk_cache.get(key)

        if cached is not None:
            diffs.append(cached.model_copy(update={"section_id": section_id}))
            continue

        diff = chunked_lector.extract_chapter(
            deep_config, section_id=section_id, text=body, entities_so_far=entities
        )
        if chunk_cache is not None and key is not None:
            chunk_cache.put(key, diff)
        diffs.append(diff)
    return diffs


def _section_arcs(text: str, *, segments: int) -> list[SectionArc]:
    """A ShapeMatch per chapter, for a chaptered text. Empty for a flat story."""
    chs = structure.chapters(text)
    if len(chs) <= 1:
        return []
    return [
        SectionArc(section_id=cid, level="chapter", title=title, shape=arc.classify(body, segments=segments))
        for cid, title, body in chs
    ]
