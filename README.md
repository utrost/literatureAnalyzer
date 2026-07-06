# Literature Analyzer — Phase 0

Deconstruct a human-written story into its structure. The inverse of the
[Endless](https://github.com/utrost/Endless) story engine: Endless turns
*structure into prose*; this turns *prose back into structure*.

Feed it a story and it reconstructs the four artifacts Endless is built around —
using the **same schemas**, so what this produces is what Endless consumes.
Analyze a story you love, then regenerate in its shape and voice.

## What it extracts

| artifact | how | what you get |
|---|---|---|
| **Shape** | deterministic | the emotional arc, sampled and matched to the Reagan six (man_in_hole, cinderella, tragedy, rags_to_riches, icarus, oedipus) |
| **Style** | deterministic | a `StyleProfile` — sentence length, variance, diction, Latinate density, psychic distance, show/tell, dialogue attribution — plus voice exemplars |
| **World** | LLM (`--deep`) | a `WorldSeed` — characters, wants, secrets, locations, Chekhov objects |
| **Beats** | LLM (`--deep`) | a `BeatPlan` — the story segmented into functional beats |

Shape and Style are **deterministic** — no model, no network, no API key. World
and Beats need a model and run only under `--deep`.

## Quick start

```bash
uv sync
uv run deconstruct examples/the_lantern.txt
```

Output is a Markdown report: the arc as a sparkline, the shape ranking, and the
measured style axes. Add `-f json` for the raw `StoryAnalysis`, or `-o report.md`
to write it to a file.

## Deep mode (world + beats)

The LLM passes need the `deep` extra and a configured model:

```bash
uv sync --extra deep
cp config.example.yaml config.yaml     # point it at a pulled Ollama model
uv run deconstruct examples/the_lantern.txt --deep
```

`provider: ollama` is auto-normalized to `ollama_chat`, and local models use
Instructor's JSON mode — the same lessons Endless learned the hard way apply here.

**Deep results are cached.** The LLM world/beats land in a content-addressed
store under `out/analyses/<hash>/` (keyed on the source text), so re-running the
same story reuses them instead of re-calling the model. The world is reused
whenever present; beats are reused only if `--segments` is unchanged. Pass
`--fresh` to recompute, `--store-dir` to relocate the cache. The artifacts are
plain JSON — hand-edit `world.json` and the next run honors your edit
(modify-then-reuse). The deterministic passes are instant, so they're never cached.

## The contract with Endless

The output schemas (`Shape`, `StyleProfile`, `WorldSeed`, `BeatPlan`) are copied
from Endless deliberately. The loop:

```
human story ──▶ [Literature Analyzer] ──▶ Shape + Style + World + Beats
                                                    │
                                                    ▼
                                          [Endless] ──▶ new story in the same shape & voice
```

## How the deterministic passes work

- **Arc** (`arc.py`): sentiment is sampled across word-balanced windows using a
  small built-in polarity lexicon (bag-of-words, à la Reagan et al. 2016),
  smoothed, normalized, then compared to each reference curve by z-scored RMSE.
  Crude but honest — it reliably separates rising arcs from falling ones.
- **Style** (`metrics.py`): every axis is a transparent, dependency-free proxy
  (sentence lengths, modifier density, Latinate suffixes, pronoun mix). Raw
  numbers come back as `StyleEvidence` so nothing is hidden.

Both are documented as approximations. Sharper sentiment and an LLM-authored
style brief are on the phase ladder — see [`literature_analyzer_design.md`](./literature_analyzer_design.md).

## Tests

```bash
uv run pytest
```

Deterministic only (no LLM calls), mirroring Endless's testing discipline.
