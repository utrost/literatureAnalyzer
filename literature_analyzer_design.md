# Literature Analyzer — Design Document

*Personal project. Audience of one. Status: draft v0.1 — phase 0 shipped. The
companion to [Endless](https://github.com/utrost/Endless); read that project's
`story_engine_design.md` first, because this one is defined by inversion.*

---

## 1. Purpose

Endless generates stories from structure. This does the opposite: it takes a
finished, human-written story and recovers the structure underneath it — the
emotional arc, the prose style, the world, and the beats.

Two reasons to want that:

1. **Learning by disassembly.** The fastest way to understand why a story works
   is to see its skeleton. What shape is it? Where's the low point? How long are
   the sentences, and how much does the narrator tell versus show?
2. **Closing the loop with Endless.** If the deconstruction speaks Endless's
   schema, then analyzing a story you love yields a `Shape` + `StyleProfile` +
   `WorldSeed` + `BeatPlan` you can hand straight to Endless to generate *new*
   stories in that shape and voice. Analysis feeds synthesis.

### Success criteria (audience of one)

- I point it at a story and the shape it reports matches my own read.
- The style profile is specific enough that Endless, fed it, writes in a
  recognizably similar voice.
- The deterministic passes run instantly, offline, with no API key.
- The output drops into Endless without a translation layer.

### Non-goals

- Literary criticism or interpretation. This reports structure, not meaning.
- A general NLP toolkit. Narrow tool, narrow job.
- Multi-user anything. Single user, single machine, same as Endless.

---

## 2. Core Thesis

Endless's thesis is that **shape** (what should happen) and **graph** (what can
happen) are the two structural layers that make long-form generation cohere.
The corollary, and this project's thesis: those same two layers can be
*recovered* from finished prose. A story is a projection of structure into
language; deconstruction is the inverse projection.

Some of that inverse is deterministic — you can measure sentence length and
sample sentiment with arithmetic, no model required. Some needs a reader's
judgment — who wants what, which object is a Chekhov gun — and that's where an
LLM earns its place. The determinism boundary from Endless (§13 there) applies
here unchanged.

---

## 3. Inspirations & Prior Art

Same lineage as Endless. Vonnegut's "Shapes of Stories" for the idea that arcs
have measurable form; **Reagan et al. 2016** for the empirical version —
bag-of-words sentiment over ~1,300 Gutenberg texts, six shapes falling out of
SVD. This project's arc pass is a small, honest homage to that method: crude
lexicon sentiment, sampled and matched. Reagan's own note was "crude; but it
worked," and phase 0 takes that permission.

The world-graph extraction is the **Lector** that Endless's own design doc
defers to its v1 (§4 there, the per-beat extractor). Here it's a first-class
role, because extraction *is* the product rather than a consistency check.

---

## 4. System Architecture

Data flow, the mirror of Endless's pipeline:

```
human-written story (plain text)
        │
        ▼
  ┌───────────────┐
  │  Segmenter    │  code — words / sentences / windows
  └───────┬───────┘
          │
   ┌──────┴───────────────────────────────┐
   ▼                                       ▼
┌────────────────┐                 ┌────────────────┐
│ Arc classifier │  code           │ Prose metrics  │  code
│ prose → Shape  │                 │ prose → Style  │
└───────┬────────┘                 └───────┬────────┘
        │                                  │
        │        ┌────────────────┐        │
        │        │    Lector      │  LLM   │   (--deep)
        │        │ prose → World  │        │
        │        └───────┬────────┘        │
        │        ┌───────┴────────┐        │
        │        │ Beat labeler   │  LLM   │   (--deep)
        │        │ prose → Beats  │        │
        │        └───────┬────────┘        │
        └────────────────┼─────────────────┘
                         ▼
                 ┌────────────────┐
                 │ StoryAnalysis  │  → Markdown / JSON
                 └────────────────┘
```

### 4.1 Role inversion

Every role here is an Endless role run backwards. This is the whole design in
one table:

| Endless role | direction | Analyzer role | direction | determinism |
|---|---|---|---|---|
| Shape selector | pick an arc | **Arc classifier** | measure the arc | deterministic |
| Author | style → prose | **Prose metrics** | prose → style | deterministic |
| World Seeder | seed → world | **Lector** | prose → world | LLM |
| Planner | shape → beats | **Beat labeler** | prose → beats | LLM |

The top two run always and offline. The bottom two run under `--deep` with a
configured model. `StoryAnalysis` bundles all four (world/beats `None` without
`--deep`).

---

## 5. Data Models

The four contract types — `Shape`, `StyleProfile`, `WorldSeed`, `BeatPlan` — are
copied from Endless's `schemas.py` verbatim and must not drift. That copy is the
contract; if Endless changes a field, change it here too. `schemas.py` marks the
boundary between the shared contract and the analysis-only additions
(`ArcSample`, `ShapeMatch`, `ShapeScore`, `StyleEvidence`, `StoryAnalysis`).

Analysis-only types exist because deconstruction produces things generation
never needs: a sampled curve, a ranked list of candidate shapes with distances,
and the raw measurements behind each style axis (kept for transparency — every
proxy is auditable).

---

## 6. The determinism boundary

Copied wholesale from Endless §13, because it's the same boundary:

- **Deterministic (code).** Segmentation, arc sampling and classification, style
  metrics. Pure functions of the text. Fully unit-tested, no model, no network.
- **Model (LLM).** World extraction, beat labeling. Judgment calls. Behind
  `--deep`, behind the `deep` optional dependency, lazy-imported so the base
  package installs and tests with zero LLM dependencies.

This is why the base install is three packages (pydantic, typer, pyyaml) and the
test suite runs offline in a fraction of a second.

---

## 7. Known crudeness (phase 0, on purpose)

Being honest about the proxies, so nobody mistakes them for more than they are:

- **Sentiment is bag-of-words** off a ~250-word built-in lexicon. It traces the
  gross shape of an arc and reliably separates rising from falling stories, but
  it under-reads a "bottom" when the despairing passage still contains warm
  words (a grief scene full of "loved" and "home" reads less low than it is).
  On the bundled `the_lantern.txt` it ranks the three rise-ending shapes on top
  — directionally right — but places cinderella above man_in_hole.
- **Several style axes are heuristic defaults.** Diction register and psychic
  distance are hard deterministically; they get pronoun/contraction-based
  guesses. The raw numbers are exposed as `StyleEvidence` so the guess is never
  hidden.
- **Sentence splitting is regex.** "Mr. Toad" is two sentences to it.

None of this is load-bearing for the phase-0 thesis (does the loop with Endless
work end to end?), and all of it is on the ladder below.

---

## 8. Deconstruction dimensions

"Deconstruct a story" is underspecified — a story decomposes along many axes, and
the tool has to *choose* which ones to chase rather than boil the ocean. This
section is the map: every dimension worth extracting, and the one principle that
ranks them.

### 8.1 The ranking principle: does Endless consume it?

The tool's leverage is the contract — its output is Endless's input (§5). So each
dimension is one of two kinds:

- **Contract dimensions** — things Endless can already *generate from*. Extracting
  these closes the loop (analyze → regenerate → compare, §9 v1). Highest value,
  because analysis compounds with synthesis.
- **Analysis-only dimensions** — genuinely illuminating, but Endless has no slot
  for them. A lens, not a loop. Worth building, but they don't compound with the
  generation side until Endless grows a matching capability. Adding one is often a
  *joint* change: a new extractor here **and** a new consumption slot in Endless.

Chase contract dimensions first. An analysis-only dimension is only worth it when
its insight value is high enough to justify not closing a loop.

### 8.2 The dimension map

| Dimension | What it captures | Kind | Endless slot | Status |
|---|---|---|---|---|
| **Story arc / shape** | emotional trajectory, matched to the Reagan six | contract | `Shape` | ✅ shipped (deterministic) |
| **Prose style** | sentence/diction/distance axes + exemplars | contract | `StyleProfile` | ✅ shipped (deterministic) |
| **Characters (flat)** | wants, appearance, secret, one emotional snapshot | contract | `WorldSeed.characters` | ✅ shipped (`--deep`) |
| **Locations** | the places the action occupies | contract | `WorldSeed.locations` | ✅ shipped (`--deep`) |
| **Objects / Chekhov guns** | props that carry narrative weight | contract | `WorldSeed.chekhov_objects` | ✅ shipped (`--deep`) |
| **Beats** | functional segmentation of the plot | contract | `BeatPlan` | ✅ shipped (`--deep`) |
| **Character development** | each character's *change* across the story | contract† | — (needs new field) | ⏳ next (v1) |
| **Act hierarchy** | acts → sequences → scenes nesting the flat beats | contract† | — (needs nested `BeatPlan`) | ⏳ v1 |
| **Relationships / social graph** | who's tied to whom, and how it shifts | contract† | — (needs edges on the graph) | later |
| **Timeline / chronology** | story-time vs. narration-order; flashbacks, threads | analysis-only‡ | — | later |
| **Themes / motifs** | recurring images and the question it circles | analysis-only | — | later |

† *Contract-adjacent:* a contract dimension in spirit, but the matching Endless
slot doesn't exist yet, so shipping it is a joint change across both repos.
‡ *Analysis-only until* Endless can generate non-linearly.

### 8.3 What Phase 0 extracts today, and its shallowness

Six dimensions ship, but three of them are **flat where the story is deep**:

- A **character** is a static snapshot — one `wants`, one `emotional_state`. But a
  story is precisely the *change* in that snapshot. This is the single biggest
  gap, and §9's v1 addresses it first.
- **Beats** are a flat list, when real structure nests (acts → scenes → beats).
- The **social graph** is implicit — secrets carry a `known_by`, but there are no
  relationship edges.

### 8.4 The recommended order (feeds the phase ladder)

1. **Character development.** Reuse the beat segmentation already extracted:
   sample each character's emotional state per beat, track want→need shifts and
   relationship changes. Turns flat characters into arcs — highest
   insight-per-effort. Joint change: add a trajectory to `Character` here **and**
   a consumption slot in Endless. This *is* the v1 round-trip work in §9.
2. **Act hierarchy.** Make beats nest. Small schema change (a tree instead of a
   list), a clearer structural picture, and act boundaries Endless can read as a
   pacing budget.
3. **Relationships** when multi-character stories demand it.
4. **Timeline** and **themes** last — high insight, but analysis-only until
   Endless can consume them, so they don't compound with the generation side yet.

The rule of thumb: **deepen the contract before widening into analysis-only.** A
tool that deconstructs a story into exactly what its sibling can rebuild is worth
more than one that reports ten disconnected views.

---

## 9. Build phases

**v0 — Phase 0. ✅ shipped.**
- Deterministic arc classifier (sampled sentiment → Reagan six by z-scored RMSE).
- Deterministic prose metrics → `StyleProfile` + `StyleEvidence` + exemplars.
- LLM Lector and beat labeler behind `--deep`, with versioned prompts.
- `deconstruct` CLI (Markdown + JSON), packaged as `lit_analyzer`.
- Schema contract with Endless; deterministic-only test suite.

**v0.5 — Sharper measurement.** Replace the bag-of-words lexicon with a real
sentiment model (VADER, NRC-VAD, or a cheap LLM sentiment pass) and measure
whether classification accuracy on hand-labeled stories improves. Better
sentence segmentation. An LLM-authored style brief in `--deep` that reads richer
than the templated one. This is the analog of Endless's v0.5 "quality close."

**v1 — Round-trip fidelity.** Close the loop for real: analyze a story, feed the
output to Endless, generate, re-analyze the generated story, and measure how
close the second analysis lands to the first. That round-trip distance is the
honest end-to-end metric for both projects at once. Add a corpus + a small
labeled eval set so classification and style measurement can be scored, not
vibed — the mirror of Endless's eval harness.

**v2 — Comparative deconstruction.** Analyze many stories, cluster by shape and
style, surface an author's fingerprint across a body of work. Diff two stories'
structures. This is where the tool stops being a single-story lens and becomes a
way to see a whole shelf.

---

## 10. What's NOT here yet

Real sentiment model, labeled eval set, round-trip fidelity metric, corpus-level
comparison, better sentence segmentation, per-character voice extraction. The
dimensions still on the map — character development, act hierarchy, relationships,
timeline, themes — are laid out in §8; the sequencing is in §9.
