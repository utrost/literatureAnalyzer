from pathlib import Path

import pytest

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "the_lantern.txt"


@pytest.fixture
def lantern_text() -> str:
    return EXAMPLE.read_text()
