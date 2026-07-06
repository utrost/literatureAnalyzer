"""Bridge to Endless — emit an analysis as artifacts Endless generates from.

Closes the round-trip (design doc §8.5) with plumbing instead of hand-copying.
A deconstruction's `WorldSeed`, `BeatPlan`, and `StyleProfile` are already in
Endless's schemas (the shared contract), so "emitting" is just writing them in
the layout Endless consumes:

    <dest>/
        runs/<run_id>/
            meta.json     # seed, shape, style, total_words — an Endless run header
            world.json    # WorldSeed — Endless --resume loads this, skips seeding
            plan.json     # BeatPlan  — Endless --resume loads this, skips planning
        styles/<name>.yaml  # StyleProfile — drop into Endless's data/styles
        HOWTO.md            # the three copy steps + the resume command

The bundle is portable: it doesn't touch or assume the location of an Endless
checkout. HOWTO.md spells out where each file goes. Because Endless's Author
loads the style by name from its config, the emitted style is given a real name
(from the source filename) so `story.style: <name>` can reference it.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from .schemas import StoryAnalysis


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "extracted"


@dataclass
class EmitResult:
    dest: Path
    run_id: str
    style_name: str
    run_dir: Path
    style_path: Path


def emit_endless(
    analysis: StoryAnalysis, dest: Path, *, style_name: str | None = None
) -> EmitResult:
    """Write ``analysis`` as an Endless-consumable handoff bundle under ``dest``.

    Requires the ``--deep`` artifacts (world + beats); a deterministic-only
    analysis has nothing for Endless to generate from.
    """
    if analysis.world is None or analysis.beats is None:
        raise ValueError(
            "emit-endless needs a world graph and beats — run the analysis with "
            "--deep first (or pass a --from analysis.json that has them)."
        )

    dest = Path(dest)
    run_id = time.strftime("%Y%m%d-%H%M%S")
    name = style_name or _slug(Path(analysis.source).stem)

    run_dir = dest / "runs" / run_id
    styles_dir = dest / "styles"
    run_dir.mkdir(parents=True, exist_ok=True)
    styles_dir.mkdir(parents=True, exist_ok=True)

    # Style, renamed so Endless config can reference it by name.
    style = analysis.style.model_copy(update={"id": f"style_{name}", "name": name})
    style_path = styles_dir / f"{name}.yaml"
    style_path.write_text(
        yaml.safe_dump(style.model_dump(), sort_keys=False, allow_unicode=True)
    )

    # World + plan in Endless's run layout (plan.json is Endless's name for beats).
    (run_dir / "world.json").write_text(analysis.world.model_dump_json(indent=2))
    (run_dir / "plan.json").write_text(analysis.beats.model_dump_json(indent=2))

    meta = {
        "run_id": run_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seed": f"deconstructed from {analysis.source}",
        "shape": analysis.shape.best,
        "style": name,
        "total_words": analysis.word_count,
        "polish": False,
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2))

    (dest / "HOWTO.md").write_text(_howto(name, run_id, analysis.source))

    return EmitResult(
        dest=dest,
        run_id=run_id,
        style_name=name,
        run_dir=run_dir,
        style_path=style_path,
    )


def _howto(name: str, run_id: str, source: str) -> str:
    return f"""# Handoff to Endless

Produced by literatureAnalyzer from: {source}

This bundle holds the extracted **world**, **beats**, and narrator **style** in
Endless's own formats. Three copy steps wire it in, then one command generates a
new story in the deconstructed shape, structure, and voice.

Let `$ENDLESS` be your Endless checkout.

1. Install the extracted style into Endless's style library:

   ```
   cp styles/{name}.yaml $ENDLESS/src/story_engine/data/styles/
   ```

2. Point Endless's config at it — in `$ENDLESS/config.yaml`:

   ```yaml
   story:
     style: {name}
   ```

3. Drop the pre-planned run into Endless:

   ```
   cp -r runs/{run_id} $ENDLESS/out/runs/
   ```

4. Generate. World-seeding and planning are skipped because `world.json` and
   `plan.json` are already present, so Endless authors straight from the
   extracted structure:

   ```
   cd $ENDLESS && uv run story --resume {run_id} --skip-preflight
   ```

The output is a new story written in the shape (`{run_id}`'s `meta.json`),
structure, and voice deconstructed from the original.
"""
