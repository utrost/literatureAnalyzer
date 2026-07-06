from lit_analyzer import metrics
from lit_analyzer.schemas import StyleProfile, StyleEvidence


def test_measure_returns_profile_and_evidence(lantern_text):
    profile, evidence = metrics.measure(lantern_text)
    assert isinstance(profile, StyleProfile)
    assert isinstance(evidence, StyleEvidence)
    assert profile.authored_brief
    assert evidence.word_count > 0
    assert evidence.sentence_count > 0


def test_axes_are_valid_enums(lantern_text):
    profile, _ = metrics.measure(lantern_text)
    ax = profile.axes
    assert ax.sentence_length_variance in {"low", "medium", "high"}
    assert ax.latinate_ratio in {"low", "medium", "high"}
    assert ax.description_density in {"sparse", "medium", "lush"}
    assert ax.diction_register in {"formal", "colloquial", "archaic", "technical"}
    assert ax.psychic_distance in {"far", "medium", "close"}
    assert ax.dialogue_attribution in {"minimal", "conventional", "elaborate"}
    assert 0.0 <= ax.show_tell_ratio <= 1.0


def test_sentence_length_mean_is_reasonable(lantern_text):
    profile, evidence = metrics.measure(lantern_text)
    assert profile.axes.sentence_length_mean == round(evidence.sentence_length_mean)
    assert 5 <= profile.axes.sentence_length_mean <= 60


def test_first_person_detected():
    text = "I walked home. I was tired. My feet ached and I wanted only to sleep."
    profile, evidence = metrics.measure(text)
    assert evidence.first_person_ratio > 0
    assert profile.axes.psychic_distance == "close"


def test_dialogue_heavy_text_flags_attribution():
    text = (
        '"Where are you going?" she asked. "Nowhere," he said. '
        '"You always say that," she said. "And I always mean it," he said. '
        '"Then why leave?" "Because staying costs more."'
    )
    profile, _ = metrics.measure(text)
    assert profile.axes.dialogue_attribution in {"conventional", "elaborate"}


def test_measure_is_deterministic(lantern_text):
    a, _ = metrics.measure(lantern_text)
    b, _ = metrics.measure(lantern_text)
    assert a.model_dump() == b.model_dump()


def test_empty_text_does_not_crash():
    profile, evidence = metrics.measure("")
    assert isinstance(profile, StyleProfile)
    assert evidence.word_count == 1  # guarded against div-by-zero
