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
(CHAPTER I…V), each with its own shape/sparkline, plus the whole-text shape.

## 2. Deep run — the chunked path

```bash
uv run deconstruct examples/the_clockmaker_of_veil_street.txt --deep \
  -f json -o clockmaker.json
```

Because the text is chaptered, `analyze()` routes through the **chunked Lector**
(one call per chapter, fed the entities-so-far) and merges the results. The
per-chapter `WorldDiff`s and the derived event log are in the JSON.

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

Record the numbers. Re-running after a prompt tweak (`prompts/chunked_lector.v1.md`)
and comparing F1 / missed_merges is how you improve resolution with data.

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

## 7. (Optional) close the loop with Endless

The S1 world can still feed the round-trip: `--emit-endless out/handoff/`, copy
into Endless, `story --resume <id>`, then re-analyze and `--compare`. See
`USER_GUIDE.md` Part 4.

---

## What a healthy run looks like

| check | healthy signal |
|---|---|
| structure | 5 chapters, each with a per-chapter arc |
| ids across chapters | Ada/Silas/Bram each one id throughout |
| event log | Ada `state_changed` several times; `secret_learned` in ch3 |
| eval | `pair_f1` high; any `missed_merges` traceable to "the old man" |
| incremental | step-6 re-run near-instant; edit last chapter → 1 re-extract |

If the ids fracture (Ada as `ada`, `the_apprentice`, `the_girl` in different
chapters) that's the signal to strengthen `prompts/chunked_lector.v1.md` on
id-reuse — and the eval's `missed_merges` will have already told you so.

## Adding real-world texts

The proxy in the hosted dev environment blocks external downloads, but your local
machine doesn't. Any chaptered public-domain text works — good picks with a small
recurring cast and clear chapter markers:

```bash
# A Christmas Carol (5 "Staves"; Scrooge + the ghosts recur)
curl -L https://www.gutenberg.org/cache/epub/46/pg46.txt -o examples/a_christmas_carol.txt
# Dr Jekyll and Mr Hyde (chaptered; the ultimate coreference test — Jekyll IS Hyde)
curl -L https://www.gutenberg.org/cache/epub/43/pg43.txt -o examples/jekyll_and_hyde.txt
```

Trim Gutenberg's header/footer, then run steps 1–6. For the eval, write a small
`*.gold.json` mapping the names/epithets each character appears under to a stable
entity id (the Jekyll/Hyde case is a deliberately brutal test of resolution).
