from pathlib import Path
from lit_analyzer.corpus import build_author_profile
from lit_analyzer.schemas import StyleProfile


def test_build_author_profile(tmp_path):
    # Create two files by the same mock author
    file_a = tmp_path / "story_a.txt"
    file_b = tmp_path / "story_b.txt"

    # Story A has short sentences
    file_a.write_text(
        "This is short. It is cool. Many short sentences here. We love short ones. "
        "They are brief. They are simple. Simple is good."
    )
    # Story B has longer sentences
    file_b.write_text(
        "This is a relatively longer sentence meant to balance out the averaging logic of our style aggregator. "
        "We are writing multiple long sentences so that the mean sentence length shifts upwards accordingly."
    )

    profile = build_author_profile([file_a, file_b], "Mock Author")

    assert isinstance(profile, StyleProfile)
    assert profile.name == "author_mock_author"
    # Average of ~3 words and ~15 words should be in the middle
    assert 5 <= profile.axes.sentence_length_mean <= 12
    # Should have extracted exemplars from the text
    assert len(profile.exemplars) > 0
