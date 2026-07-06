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
