from lit_analyzer import analyzer
from lit_analyzer.chunkcache import ChunkCache, chapter_key
from lit_analyzer.schemas import (
    Beat,
    BeatPlan,
    Character,
    StoryClassification,
    WorldDiff,
)

# Overrides so only the chunked *world* path runs — beats/classification are
# supplied, short-circuiting their LLM roles (we only test world extraction here).
_BEATS = BeatPlan(beats=[Beat(id="eq", shape_function="f", target_words=100, pov="p", required_events=["e"], mood="m")])
_CLASS = StoryClassification(structural_template="three_act")


def _analyze(text, cache):
    return analyzer.analyze(text, deep_config=object(), chunk_cache=cache, beats=_BEATS, classification=_CLASS)


def _diff(section_id):
    return WorldDiff(
        section_id=section_id,
        characters=[Character(id=f"c_{section_id}", name=section_id, appearance="x", wants="y", emotional_state="z")],
        protagonist_id=f"c_{section_id}",
    )


def test_key_depends_on_text_and_context():
    assert chapter_key("body", "ents") == chapter_key("body", "ents")
    assert chapter_key("body", "ents") != chapter_key("body2", "ents")
    assert chapter_key("body", "ents") != chapter_key("body", "ents2")  # context matters


def test_cache_roundtrips(tmp_path):
    cache = ChunkCache.open(tmp_path)
    assert cache.get("k") is None
    cache.put("k", _diff("ch1"))
    assert cache.get("k") == _diff("ch1")


def _chaptered(bodies):
    return "\n\n".join(f"CHAPTER {i + 1}\n\n{b}" for i, b in enumerate(bodies))


def test_incremental_reextracts_only_changed_chapters(tmp_path, monkeypatch):
    calls = []

    def fake_extract(cfg, *, section_id, text, entities_so_far):
        calls.append(section_id)
        return _diff(section_id)

    monkeypatch.setattr("lit_analyzer.roles.chunked_lector.extract_chapter", fake_extract)

    body = " ".join(["the light turned over the reef and the storm broke hard"] * 6)
    bodies = [body + " one", body + " two", body + " three"]
    cache = ChunkCache.open(tmp_path)

    # First run: all three chapters extracted, cache populated.
    _analyze(_chaptered(bodies), cache)
    assert len(calls) == 3

    # Re-run identical text: every chapter hits the cache — no LLM calls.
    calls.clear()
    _analyze(_chaptered(bodies), cache)
    assert calls == []

    # Edit only the LAST chapter: only it re-extracts (earlier context unchanged).
    calls.clear()
    edited = [bodies[0], bodies[1], bodies[2] + " changed"]
    _analyze(_chaptered(edited), cache)
    assert calls == ["ch3"]


def test_editing_early_chapter_cascades(tmp_path, monkeypatch):
    import hashlib

    calls = []

    def fake(cfg, *, section_id, text, entities_so_far):
        # A realistic stub: the extracted diff depends on the chapter text, so
        # editing a chapter changes its diff -> changes downstream entities-so-far.
        calls.append(section_id)
        tag = hashlib.sha256(text.encode()).hexdigest()[:6]
        return WorldDiff(
            section_id=section_id,
            characters=[Character(id=f"c_{section_id}", name=tag, appearance="x", wants="y", emotional_state="z")],
            protagonist_id=f"c_{section_id}",
        )

    monkeypatch.setattr("lit_analyzer.roles.chunked_lector.extract_chapter", fake)
    body = " ".join(["the keeper climbed the ninety seven steps once more"] * 6)
    bodies = [body + " a", body + " b", body + " c"]
    cache = ChunkCache.open(tmp_path)
    _analyze(_chaptered(bodies), cache)

    calls.clear()
    # Edit the FIRST chapter -> its diff changes -> entities-so-far shift ->
    # every later chapter's key changes too. The edit cascades downstream.
    edited = [bodies[0] + " changed", bodies[1], bodies[2]]
    _analyze(_chaptered(edited), cache)
    assert calls == ["ch1", "ch2", "ch3"]
