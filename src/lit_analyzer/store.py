"""Artifact store — never re-pay for an LLM pass.

The deterministic passes (arc, metrics) are instant and offline, so they're
never cached — recomputing is cheaper than a disk read. The ``--deep`` passes
(Lector, beat labeler) are LLM calls, and *those* we persist, the same lesson
Endless's ``checkpoint.py`` opens with ("never lose a 12-minute run").

The store is content-addressed: the key is a hash of the source text, so the
same story always lands in the same directory and re-running reuses its world
and beats instead of re-calling the model. Editing the text yields a new key
(correct — it's a different story). The artifacts are plain JSON on disk, so
they're inspectable and hand-editable: change ``world.json`` and the next run
honors your edit instead of re-extracting (modify-then-reuse, like Endless's
``--resume`` on an edited ``world.json``).

    out/analyses/<key>/
        meta.json        # source, text_sha, segments, shape, timestamps
        world.json       # WorldSeed   (Lector output)
        beats.json       # BeatPlan     (beat labeler output)
        analysis.json    # the full StoryAnalysis
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schemas import BeatPlan, StoryAnalysis, WorldSeed, StoryClassification

DEFAULT_STORE_DIR = Path("out/analyses")


def content_key(text: str) -> str:
    """Stable short key for a piece of source text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


@dataclass
class AnalysisStore:
    root: Path

    @classmethod
    def open(cls, base: Path, text: str) -> "AnalysisStore":
        root = base / content_key(text)
        root.mkdir(parents=True, exist_ok=True)
        return cls(root=root)

    # ---- world -------------------------------------------------------------
    def load_world(self) -> WorldSeed | None:
        p = self.root / "world.json"
        return WorldSeed.model_validate_json(p.read_text()) if p.exists() else None

    def save_world(self, world: WorldSeed | None) -> None:
        if world is not None:
            (self.root / "world.json").write_text(world.model_dump_json(indent=2))

    # ---- beats -------------------------------------------------------------
    def load_beats(self) -> BeatPlan | None:
        p = self.root / "beats.json"
        return BeatPlan.model_validate_json(p.read_text()) if p.exists() else None

    def save_beats(self, beats: BeatPlan | None) -> None:
        if beats is not None:
            (self.root / "beats.json").write_text(beats.model_dump_json(indent=2))

    # ---- classification ----------------------------------------------------
    def load_classification(self) -> StoryClassification | None:
        p = self.root / "classification.json"
        return StoryClassification.model_validate_json(p.read_text()) if p.exists() else None

    def save_classification(self, classification: StoryClassification | None) -> None:
        if classification is not None:
            (self.root / "classification.json").write_text(classification.model_dump_json(indent=2))

    # ---- full analysis -----------------------------------------------------
    def load_analysis(self) -> StoryAnalysis | None:
        p = self.root / "analysis.json"
        return StoryAnalysis.model_validate_json(p.read_text()) if p.exists() else None

    def save_analysis(self, analysis: StoryAnalysis) -> None:
        (self.root / "analysis.json").write_text(analysis.model_dump_json(indent=2))

    # ---- meta --------------------------------------------------------------
    def read_meta(self) -> dict[str, Any]:
        p = self.root / "meta.json"
        return json.loads(p.read_text()) if p.exists() else {}

    def write_meta(self, **fields: Any) -> None:
        meta = self.read_meta()
        meta.update(fields)
        meta["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        meta.setdefault("created_at", meta["updated_at"])
        (self.root / "meta.json").write_text(json.dumps(meta, indent=2))
