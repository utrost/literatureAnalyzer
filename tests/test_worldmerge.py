from lit_analyzer import worldmerge
from lit_analyzer.schemas import (
    Character,
    ChekhovObject,
    Location,
    Secret,
    WorldDiff,
)


def _c(id, name, state="steady", secret=None):
    return Character(id=id, name=name, appearance="x", wants="freedom", emotional_state=state, secret=secret)


def test_single_diff_becomes_world():
    d = WorldDiff(section_id="ch1", characters=[_c("mara", "Mara")], protagonist_id="mara")
    w = worldmerge.merge_world([d])
    assert [c.id for c in w.characters] == ["mara"]
    assert w.protagonist_id == "mara"


def test_same_id_across_chapters_merges_state_evolves():
    d1 = WorldDiff(section_id="ch1", characters=[_c("mara", "Mara", state="hopeful")], protagonist_id="mara")
    d2 = WorldDiff(section_id="ch2", characters=[_c("mara", "Mara", state="broken")])
    w = worldmerge.merge_world([d1, d2])
    assert len(w.characters) == 1  # one Mara, not two
    assert w.characters[0].emotional_state == "broken"  # latest chapter wins
    assert w.characters[0].wants == "freedom"  # identity from first


def test_name_resolution_backstop_merges_forgotten_ids():
    # ch2 gave Mara a different id; normalized-name backstop still merges her
    d1 = WorldDiff(section_id="ch1", characters=[_c("mara", "Mara")], protagonist_id="mara")
    d2 = WorldDiff(section_id="ch2", characters=[_c("the_keeper", "Mara")])
    w = worldmerge.merge_world([d1, d2])
    assert len(w.characters) == 1
    assert w.characters[0].id == "mara"  # canonical id kept


def test_distinct_characters_stay_distinct():
    d = WorldDiff(section_id="ch1", characters=[_c("mara", "Mara"), _c("tom", "Tom")])
    w = worldmerge.merge_world([d])
    assert {c.id for c in w.characters} == {"mara", "tom"}


def test_secrets_accumulate_known_by():
    d1 = WorldDiff(section_id="ch1", secrets=[Secret(id="s1", content="the lens exists", known_by=["mara"])])
    d2 = WorldDiff(section_id="ch2", secrets=[Secret(id="s1", content="the lens exists", known_by=["tom"])])
    w = worldmerge.merge_world([d1, d2])
    assert len(w.secrets) == 1
    assert set(w.secrets[0].known_by) == {"mara", "tom"}


def test_locations_and_objects_dedup_by_id():
    d1 = WorldDiff(section_id="ch1", locations=[Location(id="light", name="Lighthouse", description="tall")],
                   chekhov_objects=[ChekhovObject(id="lens", name="spare lens", description="glass")])
    d2 = WorldDiff(section_id="ch2", locations=[Location(id="light", name="Lighthouse", description="tall")])
    w = worldmerge.merge_world([d1, d2])
    assert [l.id for l in w.locations] == ["light"]
    assert [o.id for o in w.chekhov_objects] == ["lens"]


def test_protagonist_falls_back_to_first_character():
    d = WorldDiff(section_id="ch1", characters=[_c("mara", "Mara")])  # no protagonist_id given
    w = worldmerge.merge_world([d])
    assert w.protagonist_id == "mara"


def test_entities_summary_lists_ids_for_the_next_chapter():
    d = WorldDiff(section_id="ch1", characters=[_c("mara", "Mara"), _c("tom", "Tom")])
    summary = worldmerge.entities_summary([d])
    assert "mara: Mara" in summary and "tom: Tom" in summary
    assert worldmerge.entities_summary([]) == "(none yet)"
