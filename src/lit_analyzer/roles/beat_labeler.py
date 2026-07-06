"""Beat labeler — prose → functional beats.

The inverse of Endless's Planner. Segments the story into narrative beats and
labels each with its shape function, POV, mood, and the events that actually
occur. The measured shape (from the deterministic arc pass) is handed in as a
hint so the labeler names beat functions consistent with the classified arc.
"""

from __future__ import annotations

from ..config import DeepConfig
from ..llm import call_structured, load_prompt
from ..schemas import BeatPlan

_PROMPT_FILE = "beat_labeler.v1.md"


def label_beats(cfg: DeepConfig, *, text: str, shape: str) -> BeatPlan:
    system = load_prompt(_PROMPT_FILE)
    user = f"Classified shape: {shape}\n\nStory:\n\n{text}\n"
    return call_structured(
        cfg.beat_labeler,
        system=system,
        user=user,
        response_model=BeatPlan,
    )
