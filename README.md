# Literature Analyzer — Phase 0

Deconstruct a human-written story into its structure. The inverse of the
[Endless](https://github.com/utrost/Endless) story engine: Endless turns
*structure into prose*; this turns *prose back into structure*.

Feed it a story and it reconstructs the four artifacts Endless is built around —
using the **same schemas**, so what this produces is what Endless consumes.
Analyze a story you love, then regenerate in its shape and voice.

> **New here?** The [**User Guide**](./USER_GUIDE.md) walks through both tools and
> their combined workflows (round-trip, transposition, voice transfer) end to end.

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

Output is a Markdown report — a legible dossier of everything the deconstruction
recovered: the emotional arc (an ASCII sparkline **and** a Mermaid `xychart` a
GitHub/Obsidian viewer renders inline), the shape ranking, and the measured
style axes. For a chaptered book run (`--deep`), it also renders the structural
**hierarchy** (a Mermaid `graph` of book → chapters → beats) and the story-time
**event log** (a Mermaid `timeline` of who's introduced, who changes, and when a
secret is learned — the world as a history, not a snapshot), plus a per-chapter
world roster. Diagrams are plain fenced ```mermaid blocks — no rendering
dependency, still fully deterministic. Add `-f json` for the raw `StoryAnalysis`,
or `-o report.md` to write it to a file.

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

## Reusing an analysis

```bash
# Save the full analysis, then re-render later with no recompute and no model:
uv run deconstruct examples/the_lantern.txt --deep -f json -o analysis.json
uv run deconstruct --from analysis.json                 # re-render as Markdown
```

## Transpose a story (retell it elsewhere, in another voice)

The capstone: deconstruct a story, keep its **bones**, swap its **surface**, and
regenerate. Analyze *Huckleberry Finn*, then retell it in a sci-fi setting in
another author's voice — same arc, same beats, same relationships and secrets;
new world, new narrator.

```bash
uv run deconstruct huck_finn.txt --deep \
  --transpose "a generation ship centuries into a slow voyage" \
  --directive "age Huck to a weary 40" \
  --directive "Jim is an escaped labor-android seeking legal personhood" \
  --rename jim=N-7 \
  --as-style gaiman.json \
  --emit-endless out/huck_scifi/
# gaiman.json is just an earlier `deconstruct <a Gaiman book> --deep -f json -o gaiman.json`
```

What's held fixed vs. transformed:

| kept (the story's identity) | transformed (its surface) |
|---|---|
| Shape — the emotional arc | world: names, appearance, setting |
| beat functions + order | beat events, re-concretized in the setting |
| each character's wants, relationships, secrets | narrator voice (`--as-style`) |

**How you steer it**, soft to hard:

- `--transpose "<brief>"` — the target world (the main lever).
- `--directive "..."` (repeatable) — free-text steering: change a character's age or gender, relocate a place, shift tone. Rendered into the transposed prose.
- `--rename id=NewName` (repeatable) — force an exact name, **enforced in code** after the model, so it's guaranteed.
- `--as-style <file>` — retell in a voice extracted from another author (or any saved `StyleProfile`).

Entity `id`s are preserved (and validated) through the transform, so the beats
still reference the right characters. The result flows straight into
`--emit-endless`, so Endless generates the new story. Needs the `deep` extra and
a model (`--transpose` implies `--deep`).

## The two projects — a closed loop

Literature Analyzer and [Endless](https://github.com/utrost/Endless) are inverse
halves of one system. Endless goes **structure → prose**; this goes
**prose → structure**. They share four schemas verbatim (`Shape`, `StyleProfile`,
`WorldSeed`, `BeatPlan`), so one tool's output *is* the other's input — that copy
is a deliberate contract (change a field in one, change it in both).

```
                        ┌──────────────────────────┐
   human-written  ───▶  │   Literature Analyzer    │  prose → structure
   story                │  (deconstruct)           │
                        └────────────┬─────────────┘
                                     │  Shape · Style · World · Beats
                                     ▼
                        ┌──────────────────────────┐
                        │        Endless           │  structure → prose
                        │  (narrate / generate)    │
                        └────────────┬─────────────┘
                                     │  a NEW story in the same shape & voice
                                     ▼
                     ( re-analyze it → compare structures = round-trip fidelity )
```

**Hand a deconstruction to Endless** — the `--emit-endless` bridge writes the
extracted world, beats, and style in Endless's own formats:

```bash
uv run deconstruct examples/the_lantern.txt --deep --emit-endless handoff/
# handoff/ now holds:
#   runs/<id>/{meta,world,plan}.json   — an Endless run, pre-seeded and pre-planned
#   styles/<name>.yaml                 — the extracted narrator voice
#   HOWTO.md                           — the exact copy + resume steps
```

Follow `handoff/HOWTO.md`: drop the run into Endless's `out/runs/`, the style into
its `data/styles/`, set `story.style` in Endless's config, and
`story --resume <id>` — Endless skips seeding and planning (world and beats are
already there) and writes a **new story in the deconstructed structure and voice**.

**Did the structure survive?** The fidelity critic diffs two analyses —
*structures, not texts* (regeneration is meant to reword):

```bash
uv run deconstruct original.txt --deep -f json -o original.json
# ...generate a new story in Endless from the handoff, then analyze it back...
uv run deconstruct regenerated.txt --deep --compare original.json
```

```
# Round-trip fidelity
- Overall structural fidelity: 78%
| dimension | fidelity | detail |
| shape | 100% | same shape, arc dist 0.10 |
| style |  88% | 8 axes compared |
| world |  71% | protagonist kept; chars 5→4, overlap 60% |
| beats |  80% | 5→5 beats, id overlap 80% |
```

**Who judges the result?** Two different critics, each with a home:

| question | lives in | status |
|---|---|---|
| did the structure survive the round-trip? | **here** — `--compare` diffs two `StoryAnalysis` (§8.5) | ✅ shipped |
| is the regenerated story any *good*? | **Endless** — its LLM-judge eval harness | ✅ shipped there |

See [`literature_analyzer_design.md`](./literature_analyzer_design.md) §8.5 for the
fidelity critic and §4.2 for how artifacts are stored and reused.

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
