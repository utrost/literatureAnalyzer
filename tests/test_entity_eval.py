from lit_analyzer import entity_eval
from lit_analyzer.entity_eval import Mention
from lit_analyzer.schemas import Character, WorldDiff


def test_perfect_resolution_scores_one():
    # Mara appears across three chapters: id reused twice, then a forgotten id
    # with the same name (the backstop should still merge her). Tom is distinct.
    mentions = [
        Mention(section_id="ch1", char_id="mara", name="Mara", gold_id="mara"),
        Mention(section_id="ch2", char_id="mara", name="Mara", gold_id="mara"),
        Mention(section_id="ch2", char_id="tom", name="Tom", gold_id="tom"),
        Mention(section_id="ch3", char_id="the_keeper", name="Mara", gold_id="mara"),
    ]
    s = entity_eval.score(mentions)
    assert s.pair_f1 == 1.0
    assert s.over_merges == 0 and s.missed_merges == 0
    assert s.gold_entities == 2 and s.predicted_entities == 2


def test_missed_merge_is_detected():
    # Same entity (Silas) but the second chapter calls him "the old man" with a
    # new id — name backstop can't catch it, so resolution misses the merge.
    mentions = [
        Mention(section_id="ch1", char_id="silas", name="Silas", gold_id="silas"),
        Mention(section_id="ch2", char_id="old_man", name="the old man", gold_id="silas"),
    ]
    s = entity_eval.score(mentions)
    assert s.missed_merges == 1
    assert s.pair_recall == 0.0
    assert s.predicted_entities == 2  # left as two, should be one


def test_over_merge_is_detected():
    # Two distinct characters share the name "John"; the name backstop wrongly
    # collapses them — an over-merge.
    mentions = [
        Mention(section_id="ch1", char_id="john_a", name="John", gold_id="john_smith"),
        Mention(section_id="ch2", char_id="john_b", name="John", gold_id="john_doe"),
    ]
    s = entity_eval.score(mentions)
    assert s.over_merges == 1
    assert s.pair_precision == 0.0
    assert s.predicted_entities == 1  # collapsed, should be two


def test_score_world_diffs_from_a_name_gold():
    diffs = [
        WorldDiff(section_id="ch1", characters=[Character(id="mara", name="Mara", appearance="", wants="", emotional_state="")]),
        WorldDiff(section_id="ch2", characters=[
            Character(id="mara", name="Mara", appearance="", wants="", emotional_state=""),
            Character(id="unlabeled", name="Passerby", appearance="", wants="", emotional_state=""),
        ]),
    ]
    # only Mara is labeled; the unlabeled passerby is skipped
    s = entity_eval.score_world_diffs(diffs, {"Mara": "mara"})
    assert s.mentions == 2
    assert s.pair_f1 == 1.0
