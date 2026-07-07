from lit_analyzer import analyzer, structure
from lit_analyzer.schemas import (
    Beat,
    BeatPlan,
    Character,
    StoryClassification,
    WorldSeed,
)

# Overrides so only the beats path runs (world + classification short-circuited).
_WORLD = WorldSeed(
    characters=[Character(id="x", name="X", appearance="", wants="", emotional_state="")],
    locations=[],
    protagonist_id="x",
)
_CLASS = StoryClassification(structural_template="three_act")


def _two_beats(cfg, *, text, shape):
    return BeatPlan(
        beats=[
            Beat(id="eq", shape_function="f", target_words=100, pov="p", required_events=["e"], mood="m"),
            Beat(id="fall", shape_function="g", target_words=100, pov="p", required_events=["e2"], mood="n"),
        ]
    )


def _chaptered():
    body = " ".join(["the light turned over the reef and the storm broke hard"] * 6)
    return "\n\n".join(f"CHAPTER {i + 1}\n\n{body} num{i}" for i in range(3))


def test_chaptered_book_gets_hierarchical_beats(monkeypatch):
    monkeypatch.setattr("lit_analyzer.roles.beat_labeler.label_beats", _two_beats)
    a = analyzer.analyze(_chaptered(), deep_config=object(), world=_WORLD, classification=_CLASS)
    plan = a.beats

    # flat list: 3 chapters x 2 beats, ids namespaced by chapter and unique
    ids = [b.id for b in plan.beats]
    assert ids == ["ch1_eq", "ch1_fall", "ch2_eq", "ch2_fall", "ch3_eq", "ch3_fall"]
    assert len(set(ids)) == 6

    # structure groups them: each chapter's beat_ids point at its beats
    assert plan.structure.level == "book"
    assert [c.beat_ids for c in plan.structure.children] == [
        ["ch1_eq", "ch1_fall"],
        ["ch2_eq", "ch2_fall"],
        ["ch3_eq", "ch3_fall"],
    ]
    # the hierarchy covers exactly the flat beats (no orphans, no dangling)
    assert structure.covers(plan.structure, ids)


def test_flat_story_keeps_flat_beats(monkeypatch, lantern_text):
    monkeypatch.setattr(
        "lit_analyzer.roles.beat_labeler.label_beats",
        lambda cfg, *, text, shape: BeatPlan(
            beats=[Beat(id="eq", shape_function="f", target_words=100, pov="p", required_events=["e"], mood="m")]
        ),
    )
    a = analyzer.analyze(lantern_text, deep_config=object(), world=_WORLD, classification=_CLASS)
    assert a.beats.structure is None  # a one-chapter story -> flat beat plan
    assert [b.id for b in a.beats.beats] == ["eq"]  # ids not namespaced
