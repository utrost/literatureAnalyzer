# Smoke Test — S1 chunked book-scale analysis

A runbook to exercise the S1 pipeline (chunked per-chapter world extraction →
entity-resolving merge → story-time event log → SQLite → incremental cache →
entity-resolution eval) against a **real local model**. The unit tests already
prove the deterministic core; this validates the one thing they can't — whether
the LLM extraction actually holds characters together across chapters.

Run it on a machine with the model (you, or Gemini locally). Everything is in
this repo; the fixture is `examples/the_clockmaker_of_veil_street.txt` — a
5-chapter novelette engineered to hit every feature: a protagonist (Ada) in all
five chapters, a mentor (Silas) who is called **"the old man"** in chapters II
and IV (the coreference trap), a recurring friend (Bram), an evolving emotional
state, and a **secret** (Ada's late father built the town clock) that is
introduced in chapter I and **learned by Ada in chapter III**.

---

## 0. Setup

```bash
cd literatureAnalyzer
uv sync --extra deep                       # LLM extras
cp config.example.yaml config.yaml         # point deep.* at your local model
ollama serve &                             # if not already running
# ensure the model in config.yaml is pulled, e.g. ollama pull qwen2.5:14b
```

## 1. Deterministic sanity (no model)

Confirms chapter segmentation and the multi-scale arc before spending any tokens.

```bash
uv run deconstruct examples/the_clockmaker_of_veil_street.txt
```

**Expect:** a report with a **"Structure (per-chapter arc)"** table listing `ch1…ch5`
(CHAPTER I…V), each with its own shape/sparkline, plus the whole-text shape. The
report also carries a Mermaid **`xychart`** of the arc and, under Structure, a
Mermaid **`graph`** of the book → chapter → beat hierarchy. Write it to a file and
open it on GitHub (or any Mermaid-aware viewer) to see the diagrams render:

```bash
uv run deconstruct examples/the_clockmaker_of_veil_street.txt -o clockmaker.report.md
```

## 2. Deep run — the chunked path

```bash
uv run deconstruct examples/the_clockmaker_of_veil_street.txt --deep \
  -f json -o clockmaker.json
```

Because the text is chaptered, `analyze()` routes through the **chunked Lector**
(one call per chapter, fed the entities-so-far) and merges the results. The
per-chapter `WorldDiff`s and the derived event log are in the JSON.

Render the same deep analysis as the **Markdown dossier** to eyeball it whole:

```bash
uv run deconstruct --from clockmaker.json -o clockmaker.deep.md
```

**Expect:** on top of the arc/style/world sections, a **"World history (event
log)"** with a Mermaid **`timeline`** (introduced / state_changed / secret_learned,
grouped by chapter) plus a full event table, and a **"World by chapter"** roster.
This is steps 3–4 below, but legible — the world as a *history*, rendered.

## 3. Check entity ids are consistent across chapters

```bash
uv run python - <<'PY'
import json
a = json.load(open("clockmaker.json"))
for d in a["world_diffs"]:
    print(d["section_id"], "->", [(c["id"], c["name"]) for c in d["characters"]])
print("\nMERGED CAST:", [(c["id"], c["name"]) for c in a["world"]["characters"]])
PY
```

**Good signs:** Ada carries **one id** in every chapter; Silas carries one id;
Bram one id. The merged cast has ~4 people, not a dozen duplicates.
**The interesting line:** in chapters II/IV, did "the old man" reuse Silas's id,
or mint a new one? Either is informative — the eval in step 5 quantifies it.

## 4. Read the story-time event log

```bash
uv run python - <<'PY'
import json
a = json.load(open("clockmaker.json"))
for e in a["world_events"]:
    print(f'{e["section_id"]:>4}  {e["kind"]:<14} {e["entity_kind"]:<9} {e["entity_id"]:<12} {e.get("note") or ""}')
PY
```

**Expect, roughly:** `introduced` events for Ada/Silas/the workshop/the clock in
ch1; a `secret` `introduced` early; **`state_changed`** events on Ada as her mood
turns (eager → anxious → despairing → determined → proud); and a
**`secret_learned`** event in **ch3** when Ada learns her father built the clock.
This is the payoff of the event log: the world as a *history*, not a snapshot.

## 5. Entity-resolution eval — turn "looks right" into a number

```bash
uv run python - <<'PY'
import json
from lit_analyzer import entity_eval
from lit_analyzer.schemas import WorldDiff

a = json.load(open("clockmaker.json"))
diffs = [WorldDiff.model_validate(d) for d in a["world_diffs"]]
gold = {k: v for k, v in json.load(open("examples/the_clockmaker_of_veil_street.gold.json")).items()
        if not k.startswith("_")}
score = entity_eval.score_world_diffs(diffs, gold)
print(score.model_dump_json(indent=2))
PY
```

**How to read it:**
- `pair_f1` near **1.0** → resolution held the cast together across chapters. 
- `missed_merges > 0` → the model split one entity (very likely "the old man" vs.
  "Silas" — the coreference gap S1 flags as still-open; this is *expected* and is
  exactly what the eval is for).
- `over_merges > 0` → two distinct people were wrongly collapsed (watch for this
  if you add name-colliding characters).

Record the numbers. Re-running after a prompt change and comparing F1 /
missed_merges is how you improve resolution with data.

**Measured baseline (qwen3.6:35b-mlx, chunked_lector v1):** `pair_f1 ≈ 0.85`,
`over_merges 0`, `missed_merges 8` — all from "the old man" getting a separate
`the_old_man` id instead of resolving to `silas_vane`. **`chunked_lector.v2`**
targets exactly this: the entities-so-far block now carries each character's
archetype + appearance, and the prompt has an explicit rule to resolve epithets
("the old man", "the keeper") to an established id. Re-run steps 2 (with
`--fresh`, to bypass the cache) and 5, and compare — a higher F1 / lower
`missed_merges` means the coreference change worked.

## 6. Incremental cache — re-run should be cheap

```bash
time uv run deconstruct examples/the_clockmaker_of_veil_street.txt --deep -f json -o /dev/null
```

**Expect:** far faster than step 2 — every chapter hits the SQLite chunk cache
(`out/analyses/chunks.sqlite`), so no LLM calls. To prove the incremental
property, append a sentence to the **last** chapter of a *copy* and re-run: only
that chapter should re-extract (earlier chapters' text and incoming context are
unchanged). `--fresh` forces full recompute. Inspect the cache:

```bash
sqlite3 out/analyses/chunks.sqlite "SELECT count(*) FROM chapter_diffs;"
```

## 7. Close the loop with Endless — the one-file handoff

The S1 world feeds the round-trip. The **new** path is a single self-contained
document instead of a bundle + copy dance: `--emit-endless <file> --as-doc`.

```bash
uv run deconstruct examples/the_clockmaker_of_veil_street.txt --deep \
  --emit-endless clockmaker.handoff.md --as-doc
```

**Expect:** one Markdown file — the readable dossier (arc, style, world, event-log
timeline, all the diagrams) on top, then an **"## Endless handoff"** section whose
fenced blocks are wrapped in `<!-- endless:begin world.json -->` … `end` sentinels.
Confirm all four artifacts are embedded:

```bash
grep -o 'endless:begin [^ ]*' clockmaker.handoff.md
# → meta.json, world.json, plan.json, styles/the_clockmaker_of_veil_street.yaml
```

Then in an **Endless** checkout, author straight from that one file — no copies,
no config edits:

```bash
cd $ENDLESS
uv run story --from-doc /path/to/clockmaker.handoff.md --skip-preflight
```

**Expect:** an `ingested … → run <id>, style '…', shape '…'` line, then normal
generation — Endless skips seeding and planning (the embedded `world.json` /
`plan.json` are unpacked into `out/runs/<id>/`) and writes a **new story in the
deconstructed structure and voice**. The style is installed into Endless's
`data/styles/` automatically. Lossless: the embedded blocks are the exact
shared-contract types, re-validated on ingest — the file is legible to *you* and
loadable by the machine at once.

**Close it fully (optional):** re-analyze the generated story and `--compare` it
to `clockmaker.json` for a round-trip fidelity number. See `USER_GUIDE.md` Part 4.

> The old **bundle** form still works when you'd rather have loose files: drop
> `--as-doc` and `--emit-endless out/handoff/` writes `runs/<id>/{meta,world,plan}.json`
> + `styles/<name>.yaml` + a `HOWTO.md` with the manual copy steps.

---

## What a healthy run looks like

| check | healthy signal |
|---|---|
| structure | 5 chapters, each with a per-chapter arc |
| ids across chapters | Ada/Silas/Bram each one id throughout |
| event log | Ada `state_changed` several times; `secret_learned` in ch3 |
| report | Markdown dossier renders the arc `xychart`, hierarchy `graph`, and event-log `timeline` |
| eval | `pair_f1` high; any `missed_merges` traceable to "the old man" |
| incremental | step-6 re-run near-instant; edit last chapter → 1 re-extract |
| handoff | `--as-doc` embeds all four artifacts; Endless `--from-doc` ingests and authors from them |

If the ids fracture (Ada as `ada`, `the_apprentice`, `the_girl` in different
chapters) that's the signal to strengthen `prompts/chunked_lector.v1.md` on
id-reuse — and the eval's `missed_merges` will have already told you so.

## Real novellas (already included)

Two real public-domain novellas ship in `examples/`, cleaned of Gutenberg
boilerplate — run steps 1–6 on them exactly as on the clockmaker:

| file | structure | recurring cast |
|---|---|---|
| `a_christmas_carol.txt` | preface + 5 staves (~28k words) | Scrooge, Marley, Cratchit, the three Spirits |
| `heart_of_darkness.txt` | 3 parts (~38k words) | Marlow, Kurtz, the manager |

These are the **scale + real-prose** tests (does resolution hold across a real
28k-word book?). The **clockmaker** stays the primary *eval* fixture because it
ships a verified `*.gold.json`; for the novellas, write your own small gold
(names/epithets → entity id) if you want a resolution number.

`examples/fetch_novellas.sh` fetches more (The Time Machine, Frankenstein, and
Jekyll & Hyde — the last a deliberately brutal coreference case, since its
chapters have bare titles and Jekyll *is* Hyde). Chapter detection recognizes
`CHAPTER/PART/BOOK/STAVE/CANTO` plus lone roman numerals; texts whose chapters
carry bare titles won't segment (analyzed as one chapter).
