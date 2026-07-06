from lit_analyzer import analyzer, report
from lit_analyzer.schemas import StoryAnalysis


def test_analyze_deterministic_path(lantern_text):
    result = analyzer.analyze(lantern_text, source="lantern")
    assert isinstance(result, StoryAnalysis)
    assert result.source == "lantern"
    assert result.word_count > 0
    # deterministic passes populate style + shape; deep passes stay None
    assert result.style is not None
    assert result.shape is not None
    assert result.world is None
    assert result.beats is None


def test_analyze_roundtrips_through_json(lantern_text):
    result = analyzer.analyze(lantern_text, source="lantern")
    restored = StoryAnalysis.model_validate(result.model_dump())
    assert restored == result


def test_report_renders_markdown(lantern_text):
    result = analyzer.analyze(lantern_text, source="lantern")
    md = report.render(result)
    assert md.startswith("# Deconstruction: lantern")
    assert "## Emotional arc" in md
    assert "## Style" in md
    assert result.shape.best in md
    # no world/beats sections without --deep
    assert "## World" not in md
    assert "## Beats" not in md


def test_deep_config_none_skips_llm(lantern_text):
    # Passing deep_config=None must never import or call the LLM roles.
    result = analyzer.analyze(lantern_text, deep_config=None)
    assert result.world is None
