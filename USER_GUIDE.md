# User Guide — Endless & Literature Analyzer

Two small, local, single-user tools that are inverse halves of one system:

- **[Endless](https://github.com/utrost/Endless)** turns **structure → prose** — it *generates* a story from a shape, a style, a world, and a beat plan.
- **[Literature Analyzer](https://github.com/utrost/literatureAnalyzer)** turns **prose → structure** — it *deconstructs* a finished human-written story back into those same four artifacts.

They share four data types verbatim (`Shape`, `StyleProfile`, `WorldSeed`, `BeatPlan`), so one tool's output is the other's input. That lets you close a loop: deconstruct a story you love → regenerate a new one with the same bones, in a new setting or voice.

```
   human story ──▶ [Literature Analyzer] ──▶ Shape·Style·World·Beats ──▶ [Endless] ──▶ new story
       ▲               (deconstruct)                                       (generate)        │
       └────────────────── --compare ◀── re-analyze ◀──────────────────────────────────────┘
                            = round-trip structural fidelity
```

> This guide is mirrored in both repositories. Part 2 is the analyzer, Part 3 is Endless, Part 4 is the workflows that use both.

---

## Part 1 — Setup

**Prerequisites**

- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).
- A model, only for the LLM-powered features: [Ollama](https://ollama.com/) with a capable model pulled (e.g. `ollama pull qwen2.5:14b`), or a cloud provider via LiteLLM.
- Optional (Endless audio): [Voicebox](https://github.com/jamiepine/voicebox) at `http://localhost:17493`.

**Install the analyzer**

```bash
git clone https://github.com/utrost/literatureAnalyzer && cd literatureAnalyzer
uv sync                 # deterministic core only — no model needed
uv sync --extra deep    # add this for --deep, --transpose (LLM features)
cp config.example.yaml config.yaml   # only needed for the LLM features
```

**Install Endless**

```bash
git clone https://github.com/utrost/Endless && cd Endless
uv sync
cp config.example.yaml config.yaml   # point models at your Ollama / cloud model
```

**Configuring models.** Both use the same YAML-per-role shape. The analyzer's `config.yaml` needs a `deep.lector` and `deep.beat_labeler`; Endless's needs `models.planner`, `models.world_seeder`, `models.author` (and optional `synopsizer`/`polisher`). `provider: ollama` is auto-rewritten to `ollama_chat` in both. Set `max_tokens` per role — Ollama silently truncates otherwise.

---

## Part 2 — Literature Analyzer: deconstruct a story

The command is `deconstruct`. The deterministic passes (arc + style) run instantly and offline; world and beats need `--deep` and a model.

**A quick, offline read:**

```bash
uv run deconstruct examples/the_lantern.txt
```

You get a Markdown report: the emotional arc as a sparkline, the shape ranking (which of the Reagan six it matches), and the measured style axes. Add `-f json` for the raw `StoryAnalysis`, `-o report.md` to write to a file, `--segments N` to sample the arc over more/fewer windows.

**Full deconstruction (adds world + beats):**

```bash
uv sync --extra deep
uv run deconstruct examples/the_lantern.txt --deep
```

This also extracts a `WorldSeed` (characters with wants/secrets, locations, Chekhov objects) and a `BeatPlan` (the story segmented into functional beats).

**What you get, at a glance:**

| artifact | how | contents |
|---|---|---|
| Shape | deterministic | emotional arc → nearest Reagan shape |
| Style | deterministic | `StyleProfile`: sentence length, variance, diction, Latinate, distance, show/tell, dialogue, + voice exemplars |
| World | `--deep` | characters, wants, secrets, locations, objects |
| Beats | `--deep` | functional beat plan |

**Caching & reuse.** `--deep` results are cached under `out/analyses/<hash>/` (keyed on the source text). Re-running the same story reuses its world/beats instead of re-calling the model. `--fresh` recomputes; `--store-dir` relocates the cache. The artifacts are plain JSON — hand-edit `world.json` and the next run honors your edit (modify-then-reuse).

**Reload without recomputing:**

```bash
uv run deconstruct some.txt --deep -f json -o analysis.json
uv run deconstruct --from analysis.json          # re-render, no model, no recompute
```

---

## Part 3 — Endless: generate a story

The command is `story`.

```bash
uv run story --seed "trippy sci-fi with me as protagonist"
uv run story --seed "..." --naive        # one-shot baseline (no shape/world/beats)
uv run story --seed "..." --polish       # scene-by-scene polish pass
uv run story --seed "..." --audio        # + TTS via Voicebox
uv run story --seed "..." --skip-preflight   # skip Ollama health checks (cloud-only)
```

Each run lands under `out/runs/<timestamp>/` with `meta.json`, `world.json`, `plan.json`, per-beat `scenes/`, and the final `story.txt`.

**Resume & per-beat regen.** Runs are checkpointed. Fix one beat without re-rolling the whole story:

```bash
uv run story --seed "..." --resume <run_id>                 # continue where it left off
uv run story --seed "..." --resume <run_id> --regen-beat climb   # redo just that beat
```

**Shapes & styles.** Set `story.shape` and `story.style` in `config.yaml`. Shapes: `man_in_hole`, `cinderella`, `tragedy`, `rags_to_riches`, `icarus`, `oedipus`. Styles: `plain_modern`, `noir`, `literary`, `pulp`. Add your own by dropping a YAML file into `src/story_engine/data/{shapes,styles}/`.

**Eval harness.** `uv run python evals/run.py` scores generations against a 6-criterion rubric with an LLM judge — run it before/after prompt changes.

---

## Part 4 — Workflows that use both tools

### A. Round-trip fidelity — "did the structure survive regeneration?"

```bash
# 1. Deconstruct the source (deep) and save it
uv run deconstruct original.txt --deep --emit-endless handoff/ -f json -o original.json

# 2. In Endless: install the handoff bundle and generate
cp -r handoff/runs/<id>        $ENDLESS/out/runs/
cp handoff/styles/<name>.yaml  $ENDLESS/src/story_engine/data/styles/
#   set  story.style: <name>  in $ENDLESS/config.yaml
cd $ENDLESS && uv run story --resume <id> --skip-preflight

# 3. Analyze the generated story and compare structures
uv run deconstruct $ENDLESS/out/runs/<id>/story.txt --deep -f json -o regen.json
uv run deconstruct --from regen.json --compare original.json
```

`--compare` reports per-dimension structural fidelity (shape, style, world, beats) and an overall score. It compares *bones, not words* — regeneration is meant to reword. (Whether the new story is any *good* is a separate question, answered by Endless's eval harness.)

### B. Transposition — retell a story in a new setting and voice

The headline workflow: keep a story's arc, beats, relationships, and secrets; swap its world and narrator. *Huckleberry Finn* on a generation ship, in another author's voice.

```bash
# Extract a target voice from another author first (optional):
uv run deconstruct a_gaiman_book.txt --deep -f json -o gaiman.json

# Transpose:
uv run deconstruct huck_finn.txt --deep \
  --transpose "a generation ship centuries into a slow voyage" \
  --directive "Jim is an escaped labor-android seeking legal personhood" \
  --directive "age Huck to a weary 40" \
  --rename jim=N-7 \
  --as-style gaiman.json \
  --emit-endless out/huck_scifi/

# Then generate in Endless from out/huck_scifi/ exactly as in workflow A.
```

**Steering the transposition** (soft → hard):

| lever | effect |
|---|---|
| `--transpose "<brief>"` | the target world — the main lever |
| `--directive "..."` (repeat) | free-text steering: change a character's age/gender, relocate a place, shift tone |
| `--rename id=Name` (repeat) | force an exact name — enforced in code, guaranteed |
| `--as-style <file>` | retell in a voice extracted from another author |

Shape, beat functions, and each character's wants/relationships/secrets are held fixed by construction — a transposition can't silently lose the story's identity.

### C. Voice transfer — write in an extracted voice

Voice is a special case of the contract: `deconstruct <book> --deep` extracts a `StyleProfile` (with exemplar passages); Endless's Author anchors on those exemplars. Emit the style (`--emit-endless` writes it as a `data/styles` YAML), reference it as `story.style`, and generate — the new story is written in that measured voice.

---

## Part 5 — Command reference

**`deconstruct` (Literature Analyzer)**

| option | purpose |
|---|---|
| `FILE` | the story to analyze (omit when using `--from`) |
| `-f, --format` | `markdown` (default) or `json` |
| `-o, --out` | write output to a file instead of stdout |
| `--segments N` | arc sampling windows (default 12) |
| `--deep` | add LLM world + beats (needs the `deep` extra + a model) |
| `--fresh` | ignore cached `--deep` artifacts and recompute |
| `--store-dir` | where `--deep` artifacts are cached (default `out/analyses`) |
| `--from <analysis.json>` | reload a saved analysis and re-render (no recompute) |
| `--compare <analysis.json>` | report round-trip structural fidelity vs. a saved analysis |
| `--emit-endless <dir>` | write an Endless-consumable handoff bundle |
| `--transpose "<setting>"` | retell in a new setting (implies `--deep`) |
| `--directive "..."` | steer the transposition (repeatable) |
| `--rename id=Name` | force an entity's new name (repeatable) |
| `--as-style <file>` | retell in a voice from a `StyleProfile`/`analysis.json` |
| `-c, --config` | config path (only for LLM features) |

**`story` (Endless)**

| option | purpose |
|---|---|
| `-s, --seed` | story seed / prompt (required) |
| `-o, --out` | output text path (audio lands beside it) |
| `--naive` | one-shot baseline (no shape/world/beats) |
| `--polish` | scene-by-scene polish pass (needs a `polisher` model) |
| `--audio` | synthesize audio via the configured TTS engine |
| `--resume <id>` | resume a checkpointed run |
| `--regen-beat <id>` | with `--resume`, regenerate only that beat |
| `--skip-preflight` | skip Ollama reachability/model checks |
| `-c, --config` | config path |

---

## Part 6 — Troubleshooting

- **`The --deep passes need the 'deep' extra`** (analyzer) — run `uv sync --extra deep`.
- **`preflight failed: Ollama … not reachable`** (Endless) — start `ollama serve`, or pass `--skip-preflight` for cloud-only configs.
- **`… is missing models`** — run the suggested `ollama pull`.
- **Truncated / empty output from a local model** — set `max_tokens` per role; for thinking models (Qwen3, DeepSeek-R1) set `thinking: false` on the Author/Polisher/roles to stop them burning the budget on reasoning.
- **Transpose changed entity ids** — the reskin must preserve ids; if a model drops one the transform raises. Retry, or use a stronger model for the role.
- **A crude-looking arc classification** — the deterministic sentiment is bag-of-words (honest but coarse); it reliably separates rising from falling arcs but under-reads a shallow "bottom." See the analyzer design doc §7.

---

## Part 7 — Going deeper

- Endless architecture & intent: [`story_engine_design.md`](https://github.com/utrost/Endless/blob/main/story_engine_design.md).
- Analyzer architecture & intent: [`literature_analyzer_design.md`](https://github.com/utrost/literatureAnalyzer/blob/main/literature_analyzer_design.md) — §4.2 artifacts/reuse, §8.5 the fidelity critic, §8.6 voice fidelity, §8.7 transposition.
- Each repo's `README.md` documents the actual code surface; each `CLAUDE.md` guides contributors.
