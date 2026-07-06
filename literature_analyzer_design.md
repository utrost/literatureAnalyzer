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

### 4.2 Artifacts and reuse

The determinism boundary decides what's worth persisting. The deterministic
passes are instant and offline — recomputing is cheaper than a disk read, so
they're never cached. The `--deep` passes are LLM calls, and *those* are stored,
the same lesson Endless's `checkpoint.py` opens with ("never lose a 12-minute
run").

The store (`store.py`) is **content-addressed**: the key is a hash of the source
text, so a story always lands in the same directory and a re-run reuses its
world and beats instead of re-calling the model.

```
out/analyses/<hash>/
    meta.json      # source, text_sha, segments, shape, timestamps
    world.json     # WorldSeed  — reused whenever present (depends only on text)
    beats.json     # BeatPlan   — reused only if --segments matches (beats depend on shape)
    analysis.json  # the full StoryAnalysis
```

The reuse rule follows the data dependencies: the world graph depends only on the
text (the cache key), so it's always reused; beats depend on the classified
shape, which depends on `--segments`, so they're reused only when the cached run
used the same segment count. `--fresh` forces recompute.

One hook serves three jobs. `analyze(..., world=, beats=)` lets a caller inject
those artifacts; the store passes cached ones, and — because the files are plain
JSON on disk — a *user* can hand-edit `world.json` and the next run honors the
edit instead of re-extracting. That's the same **modify-then-reuse** loop Endless
gets from editing `world.json` and `--resume`-ing. The analyzer stays a pure
function (no I/O); the store layer owns persistence.

Still manual (see §9): reloading a saved `analysis.json` to re-render without
recomputing, and a wired bridge that emits an extracted style/world *into
Endless's* library and run layout to close the round-trip (§8.5) without hand-copying.

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

A story splits into two layers, and the map has to cover both: the **story** (what
happens — events, people, world) and the **telling** (how it's narrated — voice,
perspective, tone). Phase 0 came out strong on story and thin on telling; keeping
the two layers explicit is what stops that imbalance from recurring.

**Story layer — what happens:**

| Dimension | What it captures | Kind | Endless slot | Status |
|---|---|---|---|---|
| **Emotional arc** | the *valence* trajectory, matched to the Reagan six | contract | `Shape` | ✅ shipped (deterministic) |
| **Structural template** | the *functional* plot skeleton — three-act, Freytag, hero's journey, seven-point, Save the Cat, Kishōtenketsu… | contract† | Endless beat planner / genre layer | later |
| **Characters (flat)** | wants, appearance, secret, one emotional snapshot | contract | `WorldSeed.characters` | ✅ shipped (`--deep`) |
| **Locations** | the places the action occupies | contract | `WorldSeed.locations` | ✅ shipped (`--deep`) |
| **Objects / Chekhov guns** | props that carry narrative weight | contract | `WorldSeed.chekhov_objects` | ✅ shipped (`--deep`) |
| **Beats** | functional segmentation of the plot | contract | `BeatPlan` | ✅ shipped (`--deep`) |
| **Character development** | each character's *change* across the story | contract† | — (needs new field) | ⏳ next (v1) |
| **Act hierarchy** | acts → sequences → scenes nesting the flat beats | contract† | — (needs nested `BeatPlan`) | ⏳ v1 |
| **Relationships / social graph** | who's tied to whom, and how it shifts | contract† | — (needs edges on the graph) | later |
| **Conflict / stakes** | the dramatic question; what's at risk and against what | analysis‡ | — (Endless scores it, no slot) | later |
| **Timeline / chronology** | story-time vs. narration-order; flashbacks, threads | analysis‡ | — | later |
| **Themes / motifs** | recurring images and the question it circles | analysis-only | — | later |

**Telling layer — how it's narrated:**

| Dimension | What it captures | Kind | Endless slot | Status |
|---|---|---|---|---|
| **Prose style** | sentence/diction/distance axes + exemplars | contract | `StyleProfile` | ✅ shipped (deterministic) |
| **POV / focalization** | first/third/omniscient; whose eyes, and where it shifts | contract | `Beat.pov` (shipped, unextracted!) | ⏳ next |
| **Per-character voice** | each character's idiolect, distinct from the narrator's | contract† | `Character.voice_profile_id` | later |
| **Genre** | the convention set overlaid on the shape (mystery, romance…) | contract† | Endless's genre layer (§4 there) | later |
| **Pacing** | scene-vs-summary rhythm — where time dilates and compresses | analysis‡ | — | later |
| **Tone / attitude** | irony, comic vs. tragic register, the narrator's stance | analysis-only | — | later |

† *Contract-adjacent:* a contract dimension in spirit, but the matching Endless
slot doesn't exist yet (or isn't wired), so shipping it is a joint change across
both repos.
‡ *Analysis-or-joint:* extractable and insightful now, but Endless has no slot,
so it's a lens until one is added (timeline also waits on non-linear generation).

**Emotional arc vs. structural template — two orthogonal sub-axes of "shape."**
A survey of storytelling frameworks (epubli's "15 Storytelling-Methoden": three-,
four-, five-act/Freytag, seven-point, hero's journey, Story Circle, Save the Cat,
Story Spine, Romancing the Beat, Kishōtenketsu, …) makes clear that all fifteen
are the *same kind of thing* — functional plot skeletons — and none is a new
dimension. They're templates on one axis. But they force a split we'd been
blurring: a story has **both** an emotional arc (the valence curve — what we
classify) **and** a structural template (the functional skeleton — which we
don't), and the two are independent. A three-act story can be Man-in-Hole *or*
Tragedy; the act skeleton and the fortune curve are set separately. Classifying
*which template* a story follows is a real deconstruction target, distinct from
the Reagan arc, and it feeds Endless's beat planner (plan from "hero's journey",
not just from a valence shape). Several templates are genre-bound — Romancing the
Beat is romance, Save the Cat is screen — which is exactly why **genre** and
**structural template** couple: genre selects a template.

**A boundary both tools share: the conflict-arc assumption.** The Reagan six and
Freytag alike assume a story is a *tension curve climbing to a climax*. Kishōtenketsu
(ki–shō–ten–ketsu: introduction, development, twist, reconciliation) is a
four-act structure with **no central conflict and no tension climax** — the "twist"
recontextualizes rather than confronts. Our emotional-arc classifier would force
such a story onto a valence curve it doesn't have, and Endless can't generate one.
Naming this honestly (à la §7): the whole system is currently conflict-driven by
assumption, and conflict-optional structures are outside it until both sides model
the structural-template axis rather than the valence arc alone.

### 8.3 What Phase 0 extracts today, and its shallowness

Six dimensions ship, but they are **flat where the story is deep**, and the whole
telling layer beyond prose style is missing:

- A **character** is a static snapshot — one `wants`, one `emotional_state`. But a
  story is precisely the *change* in that snapshot. This is the single biggest
  gap, and §9's v1 addresses it first.
- **Beats** are a flat list, when real structure nests (acts → scenes → beats).
- The **social graph** is implicit — secrets carry a `known_by`, but there are no
  relationship edges.
- **POV goes unextracted even though Endless already has the slot.** `Beat.pov` is
  a shipped field Endless generates from; we don't recover it. That's the cheapest
  loop to close — a contract dimension with a waiting slot and no schema work.

### 8.4 The recommended order (feeds the phase ladder)

1. **POV / focalization.** The cheapest loop to close: `Beat.pov` already exists
   in Endless, so this is extraction only — no schema change on either side.
   Detect narrative person and focalizer per beat and flag where they shift.
   Do it first because it's contract, shipped-slot, and nearly free.
2. **Character development.** Reuse the beat segmentation already extracted:
   sample each character's emotional state per beat, track want→need shifts and
   relationship changes. Turns flat characters into arcs — highest
   insight-per-effort. Joint change: add a trajectory to `Character` here **and**
   a consumption slot in Endless. This *is* the v1 round-trip work in §9.
3. **Act hierarchy + structural template.** Same structural layer, so build them
   together: make beats nest (a tree, not a list) *and* classify which named
   skeleton the nesting follows (three-act, hero's journey, seven-point…). Act
   boundaries give Endless a pacing budget; the template lets it plan from a
   skeleton, not just a valence shape.
4. **Per-character voice**, then **relationships**, when multi-character stories
   demand them — both contract-adjacent, both joint changes with Endless.
5. **Genre** classification — cheap to extract, and Endless's genre layer gives it
   a home; slot it in once the layer is wired there.
6. **Conflict/stakes, pacing, timeline, themes, tone** last — high insight, but
   analysis-or-joint until Endless has slots, so they don't compound with the
   generation side yet.

The rule of thumb: **deepen the contract before widening into analysis-only**, and
**recover a shipped Endless slot before inventing a new one.** A tool that
deconstructs a story into exactly what its sibling can rebuild is worth more than
one that reports a dozen disconnected views.

### 8.5 Closing the loop: the fidelity critic

Deconstructor (this tool) plus narrator (Endless) is two thirds of a loop. The
missing third is a **critic** that compares the original story to Endless's
regeneration. The instinct is to make that a third project. It shouldn't be —
"critic" is two different faculties, and both already have a home.

**Faculty 1 — fidelity: did the structure survive?** This does *not* compare the
two texts word-for-word; regeneration is *supposed* to produce different prose.
It compares their **deconstructions**:

```
analyze(original)     → StoryAnalysis A
analyze(regenerated)  → StoryAnalysis B
compare(A, B)         → Divergence
```

`compare` is a diff over `StoryAnalysis` — this tool's *own output type* — so it
lives here. Every dimension already carries a natural distance: shape → distance
between the two arc curves (the machinery is already in `arc.py`); style →
per-axis deltas; world → character/location overlap (did the protagonist
survive? who was dropped or invented?); beats → do the counts and functions line
up? The aggregate is the round-trip distance — the honest end-to-end metric for
*both* projects at once (§9, v1).

**Faculty 2 — quality: is the regeneration any good?** Subjective judgment against
a rubric — and **Endless already owns it**: the `evals/` harness with the
LLM-as-judge (arc, stakes, continuity, prose, POV, would-finish). Quality judgment
belongs where generation lives.

| Faculty | Question | Home | Status |
|---|---|---|---|
| Fidelity | did the structure survive the round-trip? | **here** — `compare()` (`compare.py`, `--compare`) | ✅ shipped |
| Quality | is the regenerated story good? | **Endless** — eval harness / judge | ✅ exists |

*Shipped:* `compare(a, b) → Divergence` diffs two `StoryAnalysis` into per-dimension
similarities (shape: same-best + z-scored arc distance; style: per-axis deltas;
world: name/protagonist overlap; beats: id/count overlap) and an overall score in
[0, 1]. Deterministic, offline, rendered by `report.render_divergence`. World and
beats are compared only when both sides ran `--deep`. What's still manual is the
*end-to-end automation* — the actual analyze → invoke Endless → analyze chain
crosses repos; today you bridge with `--emit-endless`, generate in Endless, then
`--compare` the two analyses. Both halves exist; only the one-command orchestration
across the two tools doesn't.

So: no third repo. A third project would duplicate Endless's judge and add a
*third* schema contract to keep in sync — cost, no benefit. The **round-trip
harness** (analyze → invoke Endless → analyze → compare) belongs here, because
this tool owns two of the three steps and is already defined as Endless's inverse;
Endless stays clean and never depends on the analyzer.

**The honest caveat.** A large round-trip distance says the loop failed but *not
which side failed* — either the analyzer mis-read the original, or Endless didn't
honor the structure it was handed. Distance alone can't attribute blame.
Disentangling the two is the real subtlety: feed Endless a *known* structure and
measure how well the analyzer recovers it, isolating the analyzer's half from the
generator's. That controlled half-loop is how the fidelity critic earns trust
before it's pointed at the full round-trip.

### 8.6 Voice fidelity: skeleton, fingerprint, author

Style is the one dimension already wired end to end — `metrics.py` extracts a
`StyleProfile`, Endless's Author writes from it. So "can we capture Hemingway vs.
Goethe and reproduce the difference?" is worth answering precisely, because it
exposes three levels of voice fidelity and where the loop currently stops.

**Level 1 — the skeleton (the axes).** The eight `StyleAxes` cleanly *separate*
terse-Hemingway from ornate-Goethe: short vs. long sentences, low vs. high
variance, colloquial vs. formal register, low vs. high Latinate, sparse vs. lush
description, minimal vs. elaborate attribution. Feed either set of numbers to
Endless and the output is recognizably terse or recognizably ornate. But the axes
are a *skeleton*: two genuinely different voices can share all eight numbers. They
miss the **syntactic architecture** (parataxis — Hemingway's "and… and…" — vs.
hypotaxis — Goethe's nested clauses), **rhythm/cadence**, **signature vocabulary**,
and **punctuation habits**. Mean sentence length is a weak proxy for clause
structure.

**Level 2 — the fingerprint (the exemplars).** The real voice rides on
`StyleProfile.exemplars` — actual passages — which is why Endless's Author prompt
calls exemplars "the truest signal." This is the difference between "short
sentences" and "*these* short sentences." **The gap (now closed, move 1 below):**
Endless was sourcing the Author's exemplars only from the *current story's* prior
scenes (drift control), and ignoring the `StyleProfile.exemplars` an analysis
hands it — so the extracted fingerprint was measured but never applied.

**Level 3 — author vs. story voice.** One analysis reads one story = that story's
*narrator* voice, not the author's. Capturing *Hemingway* means aggregating across
a **corpus** of his work and selecting *characteristic* passages — where today
`_exemplars()` just grabs the first and last paragraph. That's the v2 "author
fingerprint across a body of work" (§9).

**The three moves, in order:**

1. **Wire `StyleProfile.exemplars` → the Author** (Endless side). Small, concrete,
   highest-leverage — it's the actual broken link, the difference between terse and
   *Hemingway*-terse. *(Shipped: Endless v0.5, author prompt v2 — see that repo's
   design doc §16.)*
2. **Add syntactic axes** — a subordination/coordination ratio and a punctuation
   profile — to push the axes from skeleton toward fingerprint, so the deterministic
   read distinguishes parataxis from hypotaxis rather than only length.
3. **Corpus aggregation + characteristic-passage selection** — analyze many works
   by one author, aggregate the axes, and pick representative exemplars, to model an
   *author's* voice rather than a single story's. This is the §9 v2 work.

### 8.7 Transposition: retelling in a new setting and voice

The capstone use of everything above: deconstruct a story, keep its **bones**,
swap its **surface**, regenerate. *Huckleberry Finn* retold on a generation ship
in another author's voice — same arc, same beats, same relationships and secrets;
new world, new narrator. Transposition is a transform *between* deconstruction and
reconstruction, and because it consumes and produces the shared contract types it
lives here (`transform.py` + `roles/reskinner.py`, `roles/beat_recaster.py`),
behind `--deep`; Endless stays a pure generator.

The essential/incidental split from §8.5 is the whole design:

| held fixed (the story's identity) | transformed (its surface) |
|---|---|
| Shape — the emotional arc | world: names, appearance, the nature of places and objects |
| beat functions + order | beat events, re-concretized in the setting |
| each character's wants, relationships, secrets | narrator voice (a substituted `StyleProfile`) |

The reskinner rewrites a `WorldSeed`'s surface fields while preserving its
functional ones and — critically — **every `id`**, which the code *validates*
after the model returns, because the beats reference those ids. The beat recaster
then rewrites each beat's events to the new world while keeping `shape_function`
and order. Voice is not transformed but *substituted*: drop in a `StyleProfile`
extracted from another author (the §8.6 loop, pointed at a different corpus).

**The control surface is layered soft-to-hard**, which is the answer to "how do we
steer it":

- **setting brief** (`--transpose`) — the target world; the primary lever, prompt-level.
- **directives** (`--directive`, repeatable) — free-text steering honored literally:
  change a character's age or gender, relocate a place, shift tone. Soft, prompt-level;
  a gender/age change renders into the character's `appearance` prose.
- **renames** (`--rename id=Name`, repeatable) — a hard constraint, **enforced in
  code** after the model, so a forced name is guaranteed rather than hoped for.
- **voice** (`--as-style`) — substitute the narrator `StyleProfile`.

Preservation of shape, beat-functions, and the functional world graph is not a
lever — it's structural, so a transposition can't silently drop the story's
identity. What's hard (and where quality lives) is beat recasting: re-concretizing
an event's *method* while holding its *function* — "fakes their own death to sever
ties" must survive the jump to a new world. That's the make-or-break LLM judgment.

---

## 9. Build phases

*Scaling from short stories to book length is its own multi-phase effort spanning
both repos — see [`BOOK_SCALE_ROADMAP.md`](./BOOK_SCALE_ROADMAP.md).*

**v0 — Phase 0. ✅ shipped.**
- Deterministic arc classifier (sampled sentiment → Reagan six by z-scored RMSE).
- Deterministic prose metrics → `StyleProfile` + `StyleEvidence` + exemplars.
- LLM Lector and beat labeler behind `--deep`, with versioned prompts.
- `deconstruct` CLI (Markdown + JSON), packaged as `lit_analyzer`.
- Schema contract with Endless; deterministic-only test suite.
- **Content-addressed artifact store (§4.2):** `--deep` world/beats cached under
  `out/analyses/<hash>/`, reused on re-run, hand-editable for modify-then-reuse.
  `--fresh` recomputes. Deterministic passes stay uncached (instant).
- **Reload:** `deconstruct --from <analysis.json>` reloads a saved analysis and
  re-renders (Markdown or JSON) without recomputing. Re-running the deep passes
  over a cached base is already covered by the content-addressed store.
- **Bridge to Endless (`bridge.py`, `--emit-endless <dir>`):** writes the
  extracted `StyleProfile` as a `data/styles`-compatible `<name>.yaml` and the
  `WorldSeed`/`BeatPlan` into Endless's run layout (`runs/<id>/world.json`,
  `plan.json`, `meta.json`), plus a `HOWTO.md`. Endless's `--resume` loads
  `world.json`/`plan.json` and skips seeding/planning, so it authors straight from
  the deconstructed structure. This wires §8.5's round-trip instead of hand-copying.
- **Fidelity critic (`compare.py`, `--compare`):** diffs two `StoryAnalysis` into a
  `Divergence` — structural similarity per dimension plus an overall score (§8.5).
- **Transposition (`transform.py`, `--transpose`):** retell a deconstructed story
  in a new setting and voice, keeping shape/beats/relationships fixed (§8.7).
  Control levers: `--transpose`, `--directive`, `--rename`, `--as-style`.

**v0.5 — Sharper measurement.** Replace the bag-of-words lexicon with a real
sentiment model (VADER, NRC-VAD, or a cheap LLM sentiment pass) and measure
whether classification accuracy on hand-labeled stories improves. Better
sentence segmentation. An LLM-authored style brief in `--deep` that reads richer
than the templated one. This is the analog of Endless's v0.5 "quality close."

**v1 — Round-trip fidelity (the fidelity critic).** ✅ *The critic shipped:*
`compare()` (`--compare`) diffs two `StoryAnalysis` into a `Divergence` — the
honest end-to-end structural metric for both projects at once (§8.5). Quality
judgment is *not* duplicated here — it stays in Endless's eval harness. **Still
open:** the controlled half-loop as a *repeatable* eval (feed Endless a known
structure, measure recovery, to isolate the analyzer's error from the generator's),
one-command orchestration across the two repos, and a corpus + small labeled eval
set so classification and style measurement can be scored, not vibed.

**v2 — Comparative deconstruction.** Analyze many stories, cluster by shape and
style, surface an author's fingerprint across a body of work. Diff two stories'
structures. This is where the tool stops being a single-story lens and becomes a
way to see a whole shelf.

---

## 10. What's NOT here yet

Real sentiment model, labeled eval set, round-trip fidelity metric, corpus-level
comparison, better sentence segmentation. The dimensions still on the map — POV,
character development, act hierarchy, per-character voice, relationships, genre,
conflict/stakes, pacing, timeline, themes, tone — are laid out across the two
layers in §8; the sequencing is in §9. Also open: structural-template
classification (three-act / hero's journey / …), and lifting the conflict-arc
assumption so conflict-optional structures like Kishōtenketsu fit (§8.2).
