"""Classifier — prose → genre and structural template classification.

Reads a finished story and classifies its genre and structural plot skeleton.
"""

from __future__ import annotations

from ..config import DeepConfig
from ..llm import call_structured, load_prompt
from ..schemas import StoryClassification

_PROMPT_FILE = "classifier.v1.md"


def classify_story(cfg: DeepConfig, *, text: str) -> StoryClassification:
    system = load_prompt(_PROMPT_FILE)
    user = f"Story:\n\n{text}\n"
    return call_structured(
        cfg.classifier,
        system=system,
        user=user,
        response_model=StoryClassification,
    )
