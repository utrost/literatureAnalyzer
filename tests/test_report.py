"""Report rendering — Mermaid diagrams + S1 book-scale artifacts."""

from lit_analyzer import report
from lit_analyzer.schemas import (
    ArcSample,
    Character,
    Section,
    SectionArc,
    ShapeMatch,
    ShapeScore,
    StoryAnalysis,
    StyleAxes,
    StyleEvidence,
    StyleProfile,
    WorldDiff,
    WorldEvent,
    WorldSeed,
)


def _sm(vals, best="man_in_hole"):
    n = max(1, len(vals) - 1)
    return ShapeMatch(
        best=best,
        curve=[ArcSample(index=i, position=i / n, valence=v) for i, v in enumerate(vals)],
        ranking=[ShapeScore(shape=best, distance=0.1, confidence=0.9)],
    )


def _base(**kw):
    ax = StyleAxes(
        sentence_length_mean=14,
        sentence_length_variance="medium",
        diction_register="formal",
        latinate_ratio="medium",
        psychic_distance="close",
        show_tell_ratio=0.6,
        description_density="medium",
        dialogue_attribution="conventional",
    )
    ev = StyleEvidence(
        sentence_count=100,
        word_count=1000,
        sentence_length_mean=14.0,
        sentence_length_stdev=5.0,
        dialogue_word_ratio=0.2,
        modifier_ratio=0.1,
        latinate_ratio=0.3,
        first_person_ratio=0.0,
    )
    defaults = dict(
        source="x",
        word_count=1000,
        style=StyleProfile(id="s", name="t", axes=ax, authored_brief="brief"),
        style_evidence=ev,
        shape=_sm([0.2, 0.5, -0.3]),
    )
    defaults.update(kw)
    return StoryAnalysis(**defaults)


def test_flat_report_has_mermaid_arc():
    md = report.render(_base())
    assert "```mermaid" in md
    assert "xychart-beta" in md
    # a flat story has no hierarchy diagram, no event log
    assert "### Hierarchy" not in md
    assert "## World history" not in md


def test_chaptered_report_renders_hierarchy_and_event_log():
    structure = Section(
        id="book",
        level="book",
        title="Book",
        children=[
            Section(id="ch1", level="chapter", title="CHAPTER I", beat_ids=["ch1_eq"]),
            Section(id="ch2", level="chapter", title="CHAPTER II"),
        ],
    )
    arcs = [
        SectionArc(section_id="ch1", level="chapter", title="CHAPTER I", shape=_sm([0.2, 0.5])),
        SectionArc(section_id="ch2", level="chapter", title="CHAPTER II", shape=_sm([-0.3, -0.6])),
    ]
    events = [
        WorldEvent(seq=0, section_id="ch1", kind="introduced", entity_kind="character", entity_id="ada"),
        WorldEvent(seq=1, section_id="ch2", kind="secret_learned", entity_kind="secret", entity_id="sec", note="a: b; c"),
    ]
    diffs = [
        WorldDiff(section_id="ch1", characters=[Character(id="ada", name="Ada", appearance="", wants="", emotional_state="")]),
    ]
    md = report.render(_base(structure=structure, section_arcs=arcs, world_events=events, world_diffs=diffs))

    assert "### Hierarchy" in md
    assert "graph TD" in md
    assert "## World history (event log)" in md
    assert "timeline" in md
    assert "secret_learned" in md
    assert "CHAPTER II" in md  # section titles resolved from section_arcs
    assert "## World by chapter" in md
    # colons/semicolons in a note are sanitized so they can't break the timeline grammar
    timeline_block = md.split("```mermaid\ntimeline")[1].split("```")[0]
    assert "a: b; c" not in timeline_block
    assert "a  b  c" in timeline_block
