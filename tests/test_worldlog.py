from lit_analyzer import eventstore, worldlog
from lit_analyzer.schemas import Character, Location, Secret, WorldDiff


def _c(id, name, state="steady"):
    return Character(id=id, name=name, appearance="x", wants="y", emotional_state=state)


def test_introductions_and_state_changes_are_logged_in_order():
    diffs = [
        WorldDiff(section_id="ch1", characters=[_c("mara", "Mara", "hopeful")],
                  locations=[Location(id="light", name="Lighthouse", description="tall")]),
        WorldDiff(section_id="ch2", characters=[_c("mara", "Mara", "broken"), _c("tom", "Tom")]),
    ]
    log = worldlog.build_event_log(diffs)
    kinds = [(e.kind, e.entity_id, e.section_id) for e in log]
    assert ("introduced", "mara", "ch1") in kinds
    assert ("introduced", "light", "ch1") in kinds
    assert ("state_changed", "mara", "ch2") in kinds  # Mara's state evolved in ch2
    assert ("introduced", "tom", "ch2") in kinds
    # seq is a strict global order
    assert [e.seq for e in log] == sorted(e.seq for e in log)


def test_secret_learned_records_new_knowers():
    diffs = [
        WorldDiff(section_id="ch1", secrets=[Secret(id="s1", content="the lens", known_by=["mara"])]),
        WorldDiff(section_id="ch3", secrets=[Secret(id="s1", content="the lens", known_by=["mara", "tom"])]),
    ]
    log = worldlog.build_event_log(diffs)
    intro = [e for e in log if e.kind == "introduced" and e.entity_kind == "secret"]
    learned = [e for e in log if e.kind == "secret_learned"]
    assert len(intro) == 1 and intro[0].section_id == "ch1"
    assert len(learned) == 1
    assert learned[0].note == "tom" and learned[0].section_id == "ch3"


def test_no_spurious_state_change_when_unchanged():
    diffs = [
        WorldDiff(section_id="ch1", characters=[_c("mara", "Mara", "steady")]),
        WorldDiff(section_id="ch2", characters=[_c("mara", "Mara", "steady")]),
    ]
    log = worldlog.build_event_log(diffs)
    assert [e.kind for e in log] == ["introduced"]  # no state_changed


def test_snapshot_at_materializes_partial_world():
    diffs = [
        WorldDiff(section_id="ch1", characters=[_c("mara", "Mara")], protagonist_id="mara"),
        WorldDiff(section_id="ch2", characters=[_c("tom", "Tom")]),
    ]
    early = worldlog.snapshot_at(diffs, "ch1")
    assert {c.id for c in early.characters} == {"mara"}  # Tom not yet introduced
    full = worldlog.snapshot_at(diffs, "ch2")
    assert {c.id for c in full.characters} == {"mara", "tom"}


def test_sqlite_store_roundtrips_and_filters(tmp_path):
    diffs = [
        WorldDiff(section_id="ch1", characters=[_c("mara", "Mara", "hopeful")]),
        WorldDiff(section_id="ch2", characters=[_c("mara", "Mara", "broken")]),
    ]
    log = worldlog.build_event_log(diffs)
    db = tmp_path / "events.sqlite"
    eventstore.save_events(db, log)

    assert eventstore.load_events(db) == log  # full round-trip
    ch2 = eventstore.load_events(db, section_id="ch2")  # story-time query
    assert ch2 and all(e.section_id == "ch2" for e in ch2)


def test_sqlite_save_replaces_existing(tmp_path):
    db = tmp_path / "events.sqlite"
    d1 = [WorldDiff(section_id="ch1", characters=[_c("mara", "Mara")])]
    eventstore.save_events(db, worldlog.build_event_log(d1))
    eventstore.save_events(db, [])  # replace with empty
    assert eventstore.load_events(db) == []
