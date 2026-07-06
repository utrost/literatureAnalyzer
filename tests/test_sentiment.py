from lit_analyzer import sentiment


def test_valence_in_range():
    for t in ["", "a plain sentence about a table", "joy and ruin together"]:
        v = sentiment.valence(t)
        assert -1.0 <= v <= 1.0


def test_negation_reads_negative():
    # the upgrade over bag-of-words: "no hope" / "not happy" score negative
    assert sentiment.valence("there was no hope left, all was lost") < 0
    assert sentiment.valence("she was not happy at all") < 0


def test_clear_polarity():
    assert sentiment.valence("wonderful, joyful, triumphant delight") > 0
    assert sentiment.valence("terror, grief, death, despair") < 0


def test_deterministic():
    t = "the storm broke the lamp and the reef waited"
    assert sentiment.valence(t) == sentiment.valence(t)


def test_lexicon_fallback_still_works():
    # the zero-dependency path used if VADER is unavailable
    assert sentiment._lexicon_valence("joy love hope") > 0
    assert sentiment._lexicon_valence("grief loss death") < 0
    assert sentiment._lexicon_valence("table chair window") == 0
