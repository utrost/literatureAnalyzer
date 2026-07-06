from lit_analyzer import analyzer
from lit_analyzer.schemas import (
    Beat,
    BeatPlan,
    Character,
    WorldSeed,
    StoryClassification,
)
from lit_analyzer.store import AnalysisStore, content_key


def _world():
    return WorldSeed(
        characters=[
            Character(id="mara", name="Mara", appearance="x", wants="keep the light", emotional_state="steady")
        ],
        locations=[],
        protagonist_id="mara",
    )


def _beats():
    return BeatPlan(
        beats=[
            Beat(id="eq", shape_function="establish", target_words=100, pov="Mara", required_events=["intro"], mood="calm")
        ]
    )


def _classification():
    return StoryClassification(
        genre=["horror"],
        structural_template="three_act",
        notes="A test classification",
    )


def test_content_key_stable_and_text_sensitive():
    assert content_key("hello world") == content_key("hello world")
    assert content_key("hello world") != content_key("hello worlds")
    assert len(content_key("x")) == 12


def test_store_roundtrips_world_and_beats(tmp_path):
    store = AnalysisStore.open(tmp_path, "some story text")
    assert store.load_world() is None  # empty to start
    store.save_world(_world())
    store.save_beats(_beats())
    store.save_classification(_classification())
    assert store.load_world() == _world()
    assert store.load_beats() == _beats()
    assert store.load_classification() == _classification()


def test_store_key_isolates_different_texts(tmp_path):
    a = AnalysisStore.open(tmp_path, "story A")
    b = AnalysisStore.open(tmp_path, "story B")
    assert a.root != b.root
    a.save_world(_world())
    assert b.load_world() is None  # B's dir is untouched


def test_store_meta_tracks_fields(tmp_path):
    store = AnalysisStore.open(tmp_path, "t")
    store.write_meta(segments=12, shape="man_in_hole", source="f.txt")
    meta = store.read_meta()
    assert meta["segments"] == 12
    assert meta["shape"] == "man_in_hole"
    assert "created_at" in meta and "updated_at" in meta


def test_save_world_none_is_noop(tmp_path):
    store = AnalysisStore.open(tmp_path, "t")
    store.save_world(None)
    assert store.load_world() is None


def test_injected_world_and_beats_skip_the_llm(lantern_text):
    # deep_config is truthy, but supplied world/beats must short-circuit the
    # role calls entirely — proven by the fact that the 'deep' extra is NOT
    # installed here, so any real LLM import/call would raise.
    result = analyzer.analyze(
        lantern_text,
        deep_config=object(),  # truthy sentinel; must not be consulted
        world=_world(),
        beats=_beats(),
        classification=_classification(),
    )
    assert result.world == _world()
    assert result.beats == _beats()
    assert result.classification == _classification()
