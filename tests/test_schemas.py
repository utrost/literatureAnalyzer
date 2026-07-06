import pytest
from pydantic import ValidationError

from lit_analyzer.schemas import ArcSample, ShapeBeat, StyleAxes


def test_valence_bounds_enforced():
    ShapeBeat(id="x", valence=-1.0, function="f")
    ShapeBeat(id="x", valence=1.0, function="f")
    with pytest.raises(ValidationError):
        ShapeBeat(id="x", valence=1.5, function="f")


def test_arc_sample_position_bounds():
    ArcSample(index=0, position=0.0, valence=0.0)
    with pytest.raises(ValidationError):
        ArcSample(index=0, position=1.5, valence=0.0)


def test_style_axes_rejects_bad_enum():
    with pytest.raises(ValidationError):
        StyleAxes(
            sentence_length_mean=15,
            sentence_length_variance="enormous",  # not a valid literal
            diction_register="colloquial",
            latinate_ratio="medium",
            psychic_distance="medium",
            show_tell_ratio=0.5,
            description_density="medium",
            dialogue_attribution="conventional",
        )
