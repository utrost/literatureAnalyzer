import pytest

from lit_analyzer import analyzer, transform
from lit_analyzer.schemas import (
    ChekhovObject,
    Character,
    Location,
    WorldSeed,
)
from lit_analyzer.transform import (
    Transposition,
    _apply_renames,
    _check_ids_preserved,
    parse_renames,
    spec_block,
)


def _world():
    return WorldSeed(
        characters=[
            Character(id="jim", name="Jim", appearance="a man", wants="freedom", emotional_state="hopeful"),
            Character(id="huck", name="Huck", appearance="a boy", wants="to escape", emotional_state="restless"),
        ],
        locations=[Location(id="river", name="Mississippi", description="wide and slow")],
        chekhov_objects=[ChekhovObject(id="raft", name="raft", description="wooden")],
        protagonist_id="huck",
    )


def test_parse_renames_ok():
    assert parse_renames(["jim=N-7", "river=The Conduit"]) == {"jim": "N-7", "river": "The Conduit"}


def test_parse_renames_rejects_malformed():
    with pytest.raises(ValueError):
        parse_renames(["jim"])
    with pytest.raises(ValueError):
        parse_renames(["=nobody"])


def test_apply_renames_targets_by_id_across_entity_types():
    w = _apply_renames(_world(), {"jim": "N-7", "raft": "escape pod"})
    by_id = {c.id: c.name for c in w.characters}
    assert by_id["jim"] == "N-7"
    assert by_id["huck"] == "Huck"  # untouched
    assert w.chekhov_objects[0].name == "escape pod"
    assert w.locations[0].name == "Mississippi"  # untouched


def test_apply_renames_preserves_function_fields():
    w = _apply_renames(_world(), {"jim": "N-7"})
    jim = next(c for c in w.characters if c.id == "jim")
    assert jim.wants == "freedom"  # only the surface (name) changes
    assert jim.emotional_state == "hopeful"


def test_check_ids_preserved_passes_and_fails():
    w = _world()
    _check_ids_preserved(w.characters, w.characters, "character")  # no raise
    with pytest.raises(ValueError, match="character ids"):
        _check_ids_preserved(w.characters, w.characters[:1], "character")


def test_spec_block_surfaces_every_lever():
    spec = Transposition(
        setting="cyberpunk generation ship",
        directives=["age Huck to a weary 40", "make Tom a woman"],
        renames={"jim": "N-7"},
    )
    block = spec_block(spec)
    assert "cyberpunk generation ship" in block
    assert "age Huck to a weary 40" in block
    assert "make Tom a woman" in block
    assert "jim -> N-7" in block


def test_transpose_requires_deep_artifacts(lantern_text):
    shallow = analyzer.analyze(lantern_text, source="x")  # no world/beats
    with pytest.raises(ValueError, match="--deep"):
        transform.transpose(object(), shallow, Transposition(setting="mars colony"))


def test_transposition_defaults():
    spec = Transposition(setting="mars")
    assert spec.directives == []
    assert spec.renames == {}
    assert spec.style is None
