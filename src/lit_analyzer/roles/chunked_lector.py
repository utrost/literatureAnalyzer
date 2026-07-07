"""Chunked Lector — per-chapter world extraction (S1, book scale).

Extracts a `WorldDiff` from one chapter, given the entities already seen in
earlier chapters so recurring characters keep their ids (the primary entity
resolution mechanism; `worldmerge` is the deterministic backstop). Reuses the
Lector's model config.
"""

from __future__ import annotations

from ..config import DeepConfig
from ..llm import call_structured, load_prompt
from ..schemas import WorldDiff

_PROMPT_FILE = "chunked_lector.v2.md"


def extract_chapter(
    cfg: DeepConfig, *, section_id: str, text: str, entities_so_far: str
) -> WorldDiff:
    system = load_prompt(_PROMPT_FILE)
    user = (
        f"Section id: {section_id}\n\n"
        f"Entities already established (reuse these ids for recurring entities):\n"
        f"{entities_so_far}\n\n"
        f"Chapter text:\n\n{text}\n"
    )
    diff = call_structured(cfg.lector, system=system, user=user, response_model=WorldDiff)
    # The section_id is ours to assign, not the model's — pin it.
    return diff.model_copy(update={"section_id": section_id})
