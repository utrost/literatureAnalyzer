"""Headless edit core — typed path edits + contract validation (no LLM)."""

import pytest

from lit_analyzer import analyzer, edits
from lit_analyzer.schemas import (
    Beat,
    BeatPlan,
    Character,
    Location,
    Section,
    Secret,
    StoryAnalysis,
    WorldSeed,
)


def _analysis(lantern_text):
    world = WorldSeed(
        characters=[
            Character(id="silas", name="Silas", appearance="old", wants="the debt paid", emotional_state="wary"),
            Character(id="elara", name="Elara", appearance="young", wants="answers", emotional_state="eager"),
        ],
        locations=[Location(id="light", name="Lighthouse", description="stone")],
        secrets=[Secret(id="tithe", content="the debt is biological", known_by=["silas"])],
        protagonist_id="elara",
    )
    beats = BeatPlan(
        beats=[
            Beat(id="eq", shape_function="establish", target_words=100, pov="Elara", required_events=["intro"], mood="calm"),
            Beat(id="fall", shape_function="disruption", target_words=120, pov="Elara", required_events=["loss"], mood="tense"),
        ]
    )
    return analyzer.analyze(lantern_text, source="s", world=world, beats=beats)


def test_edit_scalar_character_field(lantern_text):
    a = edits.apply_edits(_analysis(lantern_text), ["world.characters.silas.wants=to flee the coast"])
    silas = next(c for c in a.world.characters if c.id == "silas")
    assert silas.wants == "to flee the coast"


def test_edit_list_field_splits_on_pipe(lantern_text):
    a = edits.apply_edits(_analysis(lantern_text), ["beats.fall.required_events=Silas confronts Kael|the light fails"])
    fall = next(b for b in a.beats.beats if b.id == "fall")
    assert fall.required_events == ["Silas confronts Kael", "the light fails"]


def test_edit_int_field_coerces(lantern_text):
    a = edits.apply_edits(_analysis(lantern_text), ["beats.eq.target_words=400"])
    assert next(b for b in a.beats.beats if b.id == "eq").target_words == 400


def test_edit_shape_and_protagonist(lantern_text):
    a = edits.apply_edits(_analysis(lantern_text), ["shape.best=tragedy", "world.protagonist_id=silas"])
    assert a.shape.best == "tragedy"
    assert a.world.protagonist_id == "silas"


def test_multiple_edits_apply_in_order(lantern_text):
    a = edits.apply_edits(
        _analysis(lantern_text),
        ["world.characters.elara.emotional_state=hunted", "world.characters.elara.wants=survival"],
    )
    elara = next(c for c in a.world.characters if c.id == "elara")
    assert elara.emotional_state == "hunted" and elara.wants == "survival"


def test_bad_path_raises_editerror(lantern_text):
    with pytest.raises(edits.EditError, match="no item with id"):
        edits.apply_edits(_analysis(lantern_text), ["world.characters.nobody.wants=x"])
    with pytest.raises(edits.EditError, match="unknown field"):
        edits.apply_edits(_analysis(lantern_text), ["world.characters.silas.nope=x"])


def test_malformed_spec_raises(lantern_text):
    with pytest.raises(edits.EditError, match="expected path=value"):
        edits.apply_edits(_analysis(lantern_text), ["world.characters.silas.wants"])


def test_edit_that_breaks_the_schema_is_rejected(lantern_text):
    # target_words must be > 0; setting it to 0 must fail validation, not slip through
    with pytest.raises(edits.EditError, match="invalid analysis"):
        edits.apply_edits(_analysis(lantern_text), ["beats.eq.target_words=0"])


def test_validate_contract_clean(lantern_text):
    assert edits.validate_contract(_analysis(lantern_text)) == []


def test_validate_flags_bad_protagonist_and_dangling_secret(lantern_text):
    a = _analysis(lantern_text)
    a.world.protagonist_id = "ghost"
    a.world.secrets[0].known_by = ["ghost"]
    issues = edits.validate_contract(a)
    assert any("protagonist_id" in i for i in issues)
    assert any("known_by references non-characters" in i for i in issues)


def test_validate_flags_structure_dangling_beat(lantern_text):
    a = _analysis(lantern_text)
    a.structure = Section(id="book", level="book", children=[
        Section(id="ch1", level="chapter", beat_ids=["eq", "does_not_exist"]),
    ])
    issues = edits.validate_contract(a)
    assert any("unknown beat id 'does_not_exist'" in i for i in issues)
