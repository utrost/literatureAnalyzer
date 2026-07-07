from lit_analyzer import analyzer, compare, report
from lit_analyzer.schemas import (
    Beat,
    BeatPlan,
    Character,
    Divergence,
    WorldSeed,
)


def _world(names, protagonist, locations=()):
    chars = [
        Character(id=n.lower(), name=n, appearance="x", wants="y", emotional_state="z")
        for n in names
    ]
    from lit_analyzer.schemas import Location

    return WorldSeed(
        characters=chars,
        locations=[Location(id=f"l{i}", name=l, description="d") for i, l in enumerate(locations)],
        protagonist_id=protagonist.lower(),
    )


def _beats(ids):
    return BeatPlan(
        beats=[
            Beat(id=i, shape_function="f", target_words=100, pov="p", required_events=["e"], mood="m")
            for i in ids
        ]
    )


def test_identical_analysis_is_perfect_fidelity(lantern_text):
    a = analyzer.analyze(lantern_text, source="orig")
    b = analyzer.analyze(lantern_text, source="orig")
    div = compare.compare(a, b)
    assert isinstance(div, Divergence)
    assert div.overall == 1.0
    assert div.shape.same_best
    assert div.style.similarity == 1.0
    # no --deep on either side -> no world/beats comparison
    assert div.world is None and div.beats is None


def test_overall_in_unit_range_for_different_texts(lantern_text):
    a = analyzer.analyze(lantern_text, source="a")
    b = analyzer.analyze("A short, cheerful little tale. All was well. The end.", source="b")
    div = compare.compare(a, b)
    assert 0.0 <= div.overall <= 1.0
    assert div.source_a == "a" and div.source_b == "b"


def test_style_axis_deltas_flag_differences(lantern_text):
    a = analyzer.analyze(lantern_text, source="a")
    b = analyzer.analyze(lantern_text, source="b")
    div = compare.compare(a, b)
    # same text -> every axis delta is zero
    assert all(d.distance == 0.0 for d in div.style.axes)


def test_world_compared_only_when_both_present(lantern_text):
    wa = _world(["Mara", "Tom"], "Mara", ["Lighthouse"])
    wb = _world(["Mara", "Sam"], "Mara", ["Lighthouse"])
    a = analyzer.analyze(lantern_text, source="a", world=wa, beats=_beats(["eq", "fall"]))
    b = analyzer.analyze(lantern_text, source="b", world=wb, beats=_beats(["eq", "fall"]))
    div = compare.compare(a, b)
    assert div.world is not None
    assert div.world.protagonist_match  # both Mara
    assert 0.0 < div.world.character_overlap < 1.0  # Mara shared, Tom/Sam differ
    assert div.beats is not None
    assert div.beats.id_overlap == 1.0  # same beat ids


def test_protagonist_change_is_detected(lantern_text):
    a = analyzer.analyze(lantern_text, source="a", world=_world(["Mara"], "Mara"), beats=_beats(["eq"]))
    b = analyzer.analyze(lantern_text, source="b", world=_world(["Bob"], "Bob"), beats=_beats(["eq"]))
    div = compare.compare(a, b)
    assert not div.world.protagonist_match


def test_beat_count_mismatch_lowers_beat_similarity(lantern_text):
    a = analyzer.analyze(lantern_text, source="a", world=_world(["M"], "M"), beats=_beats(["eq", "fall", "climb"]))
    b = analyzer.analyze(lantern_text, source="b", world=_world(["M"], "M"), beats=_beats(["eq"]))
    div = compare.compare(a, b)
    assert div.beats.count_a == 3 and div.beats.count_b == 1
    assert div.beats.similarity < 1.0


def test_render_divergence_markdown(lantern_text):
    a = analyzer.analyze(lantern_text, source="a")
    b = analyzer.analyze(lantern_text, source="b")
    md = report.render_divergence(compare.compare(a, b))
    assert md.startswith("# Round-trip fidelity")
    assert "Overall structural fidelity" in md
    assert "## Style axes" in md


# ---- S3: hierarchical (per-chapter) arc fidelity --------------------------------

from lit_analyzer.schemas import ArcSample, SectionArc, ShapeMatch, ShapeScore


def _arc(best, valences):
    n = max(1, len(valences) - 1)
    return ShapeMatch(
        best=best,
        curve=[ArcSample(index=i, position=i / n, valence=v) for i, v in enumerate(valences)],
        ranking=[ShapeScore(shape=best, distance=0.1, confidence=0.9)],
    )


def _section_arcs(specs):
    return [
        SectionArc(section_id=f"ch{i+1}", level="chapter", title=t, shape=_arc(best, vals))
        for i, (t, best, vals) in enumerate(specs)
    ]


def _chaptered(lantern_text, source, specs):
    a = analyzer.analyze(lantern_text, source=source)
    a.section_arcs = _section_arcs(specs)
    return a


def test_hierarchy_present_only_when_both_chaptered(lantern_text):
    flat = analyzer.analyze(lantern_text, source="flat")
    book = _chaptered(lantern_text, "book", [("I", "man_in_hole", [0.2, -0.4, 0.5])])
    assert compare.compare(flat, book).hierarchy is None  # one side flat
    assert compare.compare(book, book).hierarchy is not None


def test_identical_chapters_score_perfect_hierarchy(lantern_text):
    specs = [("I", "man_in_hole", [0.3, -0.5, 0.6]), ("II", "tragedy", [0.4, -0.2, -0.7])]
    a = _chaptered(lantern_text, "a", specs)
    b = _chaptered(lantern_text, "b", specs)
    h = compare.compare(a, b).hierarchy
    assert h.count_a == h.count_b == 2
    assert h.alignment == 1.0
    assert h.similarity == 1.0
    assert all(p.same_best for p in h.pairs)


def test_chapter_count_mismatch_penalizes_alignment(lantern_text):
    a = _chaptered(lantern_text, "a", [("I", "man_in_hole", [0.2, -0.3, 0.4])] * 4)
    b = _chaptered(lantern_text, "b", [("I", "man_in_hole", [0.2, -0.3, 0.4])] * 2)
    h = compare.compare(a, b).hierarchy
    assert h.count_a == 4 and h.count_b == 2
    assert h.alignment == 0.5  # 2 of 4 align
    assert len(h.pairs) == 2  # only the aligned chapters
    assert h.similarity < 1.0  # scaled down by alignment


def test_similar_curve_different_name_scores_partial(lantern_text):
    # cinderella (rise-fall-rise) vs man_in_hole (fall-rise) — the round-trip case:
    # different best name, but related curve → partial credit, not zero.
    a = _chaptered(lantern_text, "a", [("I", "man_in_hole", [0.5, -0.6, 0.5])])
    b = _chaptered(lantern_text, "b", [("I", "cinderella", [0.5, -0.6, 0.55])])
    p = compare.compare(a, b).hierarchy.pairs[0]
    assert not p.same_best
    assert 0.3 < p.similarity < 1.0


def test_render_shows_per_chapter_arc_table(lantern_text):
    a = _chaptered(lantern_text, "a", [("I", "man_in_hole", [0.2, -0.4, 0.5])])
    b = _chaptered(lantern_text, "b", [("I", "man_in_hole", [0.2, -0.4, 0.5])])
    md = report.render_divergence(compare.compare(a, b))
    assert "## Per-chapter fidelity" in md
    assert "| hierarchy |" in md


# ---- S3 increment 2: per-chapter beat alignment (pacing) ------------------------

from lit_analyzer.schemas import Section


def _chaptered_with_beats(lantern_text, source, specs, beats_per_ch):
    """specs = arc specs; beats_per_ch = list of beat counts, one per chapter."""
    a = _chaptered(lantern_text, source, specs)
    children, all_beats = [], []
    for i, n in enumerate(beats_per_ch):
        ids = [f"ch{i+1}_b{j}" for j in range(n)]
        children.append(Section(id=f"ch{i+1}", level="chapter", title=specs[i][0], beat_ids=ids))
        all_beats.extend(ids)
    a.structure = Section(id="book", level="book", children=children)
    a.beats = _beats(all_beats)
    return a


def test_beat_similarity_none_without_grouped_beats(lantern_text):
    # arc-only analyses (no structure/beats) → hierarchy present, pacing absent
    a = _chaptered(lantern_text, "a", [("I", "man_in_hole", [0.2, -0.3, 0.4])])
    b = _chaptered(lantern_text, "b", [("I", "man_in_hole", [0.2, -0.3, 0.4])])
    assert compare.compare(a, b).hierarchy.beat_similarity is None


def test_matching_beat_counts_score_perfect_pacing(lantern_text):
    specs = [("I", "man_in_hole", [0.3, -0.5, 0.6]), ("II", "tragedy", [0.4, -0.2, -0.7])]
    a = _chaptered_with_beats(lantern_text, "a", specs, [5, 5])
    b = _chaptered_with_beats(lantern_text, "b", specs, [5, 5])
    h = compare.compare(a, b).hierarchy
    assert h.beat_similarity == 1.0
    assert h.pairs[0].beats_a == 5 and h.pairs[0].beats_b == 5
    assert h.pairs[0].beat_similarity == 1.0


def test_pacing_drift_localizes_to_the_chapter(lantern_text):
    specs = [("I", "man_in_hole", [0.3, -0.5, 0.6]), ("II", "man_in_hole", [0.3, -0.5, 0.6])]
    a = _chaptered_with_beats(lantern_text, "a", specs, [5, 5])
    b = _chaptered_with_beats(lantern_text, "b", specs, [5, 10])  # ch2 ballooned
    h = compare.compare(a, b).hierarchy
    assert h.pairs[0].beat_similarity == 1.0          # ch1 unchanged
    assert h.pairs[1].beat_similarity == 0.5          # ch2 5 vs 10
    assert h.beat_similarity is not None and h.beat_similarity < 1.0
    md = report.render_divergence(compare.compare(a, b))
    assert "beats A → B" in md and "pacing" in md
