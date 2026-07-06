"""Beat recaster — re-concretize beats into the transposed setting.

Rewrites each beat's events so they happen in the new world and reference the
transposed entities, while keeping the beat's function, order, and the overall
plot skeleton. Reuses the beat labeler's model config (same shape of task).
"""

from __future__ import annotations

from ..config import DeepConfig
from ..llm import call_structured, load_prompt
from ..schemas import BeatPlan, WorldSeed
from ..transform import Transposition, spec_block

_PROMPT_FILE = "recast_beats.v1.md"


def recast_beats(
    cfg: DeepConfig, *, beats: BeatPlan, world: WorldSeed, spec: Transposition
) -> BeatPlan:
    system = load_prompt(_PROMPT_FILE)
    user = (
        f"{spec_block(spec)}\n\n"
        f"Transposed world (use these names and this setting):\n\n"
        f"{world.model_dump_json(indent=2)}\n\n"
        f"Original beats (recast the events; keep every id, shape_function, and the order):\n\n"
        f"{beats.model_dump_json(indent=2)}\n"
    )
    return call_structured(cfg.beat_labeler, system=system, user=user, response_model=BeatPlan)
