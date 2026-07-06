"""Reskinner — transpose a world into a new setting, structure intact.

Rewrites a WorldSeed's surface (names, appearance, the nature of places and
objects) into a target setting while preserving every id, want, relationship,
and secret. Reuses the Lector's model config (same shape of task: world work).
"""

from __future__ import annotations

from ..config import DeepConfig
from ..llm import call_structured, load_prompt
from ..schemas import WorldSeed
from ..transform import Transposition, spec_block

_PROMPT_FILE = "reskin_world.v1.md"


def reskin_world(cfg: DeepConfig, *, world: WorldSeed, spec: Transposition) -> WorldSeed:
    system = load_prompt(_PROMPT_FILE)
    user = (
        f"{spec_block(spec)}\n\n"
        f"Original world (transpose this — keep every id and protagonist_id):\n\n"
        f"{world.model_dump_json(indent=2)}\n"
    )
    return call_structured(cfg.lector, system=system, user=user, response_model=WorldSeed)
