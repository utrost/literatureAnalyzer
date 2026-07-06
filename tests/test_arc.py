import pytest

from lit_analyzer import arc
from lit_analyzer.lexicon import polarity


def test_polarity_lookup_and_inflection():
    assert polarity("joy") == 1
    assert polarity("grief") == -1
    assert polarity("unrelated") == 0
    # inflected forms resolve via suffix stripping
    assert polarity("feared") == -1
    assert polarity("smiled") == 1
    assert polarity("loving") == 1


def test_classify_returns_valid_shape(lantern_text):
    match = arc.classify(lantern_text)
    assert match.best in arc.REFERENCE_SHAPES
    # ranking covers every reference shape, best first
    assert len(match.ranking) == len(arc.REFERENCE_SHAPES)
    assert match.ranking[0].shape == match.best
    distances = [s.distance for s in match.ranking]
    assert distances == sorted(distances)


def test_curve_bounds_and_positions(lantern_text):
    match = arc.classify(lantern_text, segments=10)
    assert all(-1.0 <= s.valence <= 1.0 for s in match.curve)
    assert match.curve[0].position == pytest.approx(0.0)
    assert match.curve[-1].position == pytest.approx(1.0)
    # positions monotonically increase
    positions = [s.valence for s in match.curve]  # noqa: F841
    idxs = [s.position for s in match.curve]
    assert idxs == sorted(idxs)


def test_classify_is_deterministic(lantern_text):
    a = arc.classify(lantern_text)
    b = arc.classify(lantern_text)
    assert a.best == b.best
    assert [s.valence for s in a.curve] == [s.valence for s in b.curve]


def test_synthetic_falling_arc_reads_as_decline():
    # A text that starts joyful and ends in grief should rank a falling shape
    # (tragedy, icarus, or oedipus all end low) above a rising one.
    text = (
        ("joy love hope happy bright warm safe peace " * 8)
        + ("grief loss death ruin despair cold dark alone " * 8)
    )
    match = arc.classify(text, segments=8)
    falling = {"tragedy", "icarus", "oedipus"}
    rising = {"rags_to_riches", "cinderella"}
    best_rank = {s.shape: i for i, s in enumerate(match.ranking)}
    assert min(best_rank[s] for s in falling) < min(best_rank[s] for s in rising)


def test_empty_text_does_not_crash():
    match = arc.classify("")
    assert match.best in arc.REFERENCE_SHAPES
