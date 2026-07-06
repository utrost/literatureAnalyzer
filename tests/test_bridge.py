import json

import pytest
import yaml

from lit_analyzer import analyzer, bridge
from lit_analyzer.schemas import (
    Beat,
    BeatPlan,
    Character,
    StoryAnalysis,
    WorldSeed,
)


def _deep_analysis(lantern_text):
    """A full analysis with world+beats, without calling an LLM (inject them)."""
    world = WorldSeed(
        characters=[
            Character(id="mara", name="Mara", appearance="keeper", wants="keep the light", emotional_state="steady")
        ],
        locations=[],
        protagonist_id="mara",
    )
    beats = BeatPlan(
        beats=[
            Beat(id="eq", shape_function="establish", target_words=100, pov="Mara", required_events=["intro"], mood="calm")
        ]
    )
    return analyzer.analyze(lantern_text, source="the_lantern.txt", world=world, beats=beats)


def test_emit_writes_endless_layout(tmp_path, lantern_text):
    analysis = _deep_analysis(lantern_text)
    result = bridge.emit_endless(analysis, tmp_path)

    # run dir with the three Endless run files
    assert (result.run_dir / "world.json").exists()
    assert (result.run_dir / "plan.json").exists()
    assert (result.run_dir / "meta.json").exists()
    # style yaml + howto
    assert result.style_path.exists()
    assert (tmp_path / "HOWTO.md").exists()


def test_emitted_style_is_named_and_loadable(tmp_path, lantern_text):
    result = bridge.emit_endless(_deep_analysis(lantern_text), tmp_path)
    data = yaml.safe_load(result.style_path.read_text())
    # named after the source stem, referenceable from Endless config
    assert data["name"] == "the_lantern"
    assert data["id"] == "style_the_lantern"
    assert "axes" in data and "authored_brief" in data


def test_emitted_meta_carries_shape_and_style(tmp_path, lantern_text):
    analysis = _deep_analysis(lantern_text)
    result = bridge.emit_endless(analysis, tmp_path)
    meta = json.loads((result.run_dir / "meta.json").read_text())
    assert meta["shape"] == analysis.shape.best
    assert meta["style"] == "the_lantern"
    assert meta["total_words"] == analysis.word_count


def test_emitted_world_roundtrips_to_endless_schema(tmp_path, lantern_text):
    result = bridge.emit_endless(_deep_analysis(lantern_text), tmp_path)
    # the world.json must re-validate as a WorldSeed (the shared contract)
    world = WorldSeed.model_validate_json((result.run_dir / "world.json").read_text())
    assert world.protagonist_id == "mara"


def test_emit_requires_deep_artifacts(tmp_path, lantern_text):
    # deterministic-only analysis has no world/beats
    shallow = analyzer.analyze(lantern_text, source="x")
    with pytest.raises(ValueError, match="--deep"):
        bridge.emit_endless(shallow, tmp_path)


def test_from_reload_roundtrips(tmp_path, lantern_text):
    # save then reload an analysis.json — no recompute path
    analysis = _deep_analysis(lantern_text)
    p = tmp_path / "analysis.json"
    p.write_text(analysis.model_dump_json(indent=2))
    restored = StoryAnalysis.model_validate_json(p.read_text())
    assert restored == analysis
