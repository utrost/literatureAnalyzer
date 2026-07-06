"""Lector — prose → world graph.

The inverse of Endless's World Seeder, and the extractor Endless itself deferred
to v1. Reads a finished story and reconstructs the WorldSeed: characters (with
wants, appearance, emotional state, secrets), locations, Chekhov objects, and
secrets with who knows them.
"""

from __future__ import annotations

from ..config import DeepConfig
from ..llm import call_structured, load_prompt
from ..schemas import WorldSeed

_PROMPT_FILE = "lector.v1.md"


def extract_world(cfg: DeepConfig, *, text: str) -> WorldSeed:
    system = load_prompt(_PROMPT_FILE)
    user = f"Story:\n\n{text}\n"
    return call_structured(
        cfg.lector,
        system=system,
        user=user,
        response_model=WorldSeed,
    )
