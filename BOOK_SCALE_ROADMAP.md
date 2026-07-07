# Roadmap — Scaling to Book Length

*A planning document spanning both [Endless](https://github.com/utrost/Endless) and the [Literature Analyzer](https://github.com/utrost/literatureAnalyzer). Theoretical / not committed — a map for when the time comes. Mirrored in both repos.*

Today both tools target ~1,500-word stories. A novel is ~80,000–150,000 words. That's not a bigger version of the same job — it breaks three assumptions baked into both systems:

1. **The whole text fits in one prompt** — the Lector and beat-labeler each take the entire story in a single LLM call.
2. **Structure is flat** — `BeatPlan` is a list; `Shape` is one arc.
3. **The world is a snapshot** — `WorldSeed` is a single flat dump.

The reframe that drives the whole roadmap: **a book is not a long story; it's a tree of short ones sharing a persistent, evolving world.** So the job is to make everything **hierarchical, incremental, and retrieval-fed, with a stateful graph as the backbone.** Much of this is executing the v1/v2 already sketched in both design docs (Endless §4 graph/Lector/Editor, §5.3 event-sourcing, "v1+: SQLite event-log"; Analyzer §8.2 act hierarchy).

---

## The scaling ladder

Each rung forces specific capabilities; don't skip rungs.

| rung | length | forces |
|---|---|---|
| **R0** short story | ~1.5k | *(shipped)* |
| **R1** novelette | ~10k, 1 arc | windowed style, multi-scale arc, longer context management |
| **R2** novella | ~30k, explicit chapters | chunking, diff-merge, hierarchy, event-sourced graph |
| **R3** short novel | ~60–80k | retrieval, consistency (Editor), hierarchical planning |
| **R4** full novel | ~100k+ | incremental everything, cost/parallelism, hierarchical eval |

---

## Cross-cutting principles

- **Hierarchy over size.** Book → Part → Chapter → Scene → Beat, everywhere: the `BeatPlan` tree and a multi-scale arc (an arc per level).
- **Chunk + merge, never brute-force context.** Process a chapter at a time; merge results into a global structure. Bigger context windows are not the fix (attention degrades — "lost in the middle").
- **Stateful, event-sourced world.** Replace the flat snapshot with a temporal graph + story-time event log; materialize a snapshot at any point.
- **Retrieval, not full history.** Each bounded call pulls the *relevant* prior facts (graph queries + a vector index), not the whole book.
- **Incremental.** Edit one chapter → re-process one chapter. Chunk-level caching, not whole-text.
- **Backward compatible.** A short story is a one-node tree; every existing flow must keep working.

---

## Phases

### Phase S0 — Nestable structures *(shared contract)* — ✅ foundation shipped

The prerequisite everything else depends on. Additive schema work; no scale yet.

- **Shared contract (done):** `Section` (book/part/chapter/scene tree), `BeatPlan.structure: Section | None` (None = flat), and `Shape.children` for nested arcs — added verbatim to both repos. Every field defaults to None/empty, so all existing flows are unchanged.
- **Analyzer (done):** `segment.chapter_spans` + `structure.build_structure` produce a `Section` tree (markerless → one chapter); `analyze()` attaches `structure` and per-chapter `section_arcs` (multi-scale arc) deterministically; the report shows a per-chapter arc table.
- **Endless (done):** schema synced; the orchestrator still iterates `plan.beats`, so flat generation is untouched and a structured plan round-trips (tests confirm).
- **Beats → sections bridge (✅ done in S1):** a chaptered book now gets beats labeled *per chapter*, namespaced by section (`ch1_eq`), and nested under the structure (each chapter's `beat_ids` populated) — a hierarchical `BeatPlan`. The flat `beats` list is unchanged for existing consumers; Endless still iterates it. Per-level *generation* remains S2.
- **Exit (met):** schemas + segmentation landed; all existing tests pass unchanged; a chaptered text yields a real tree + per-chapter arcs, a short story a one-node tree.

### Phase S1 — Chunked analysis + world graph *(Analyzer)* → **R2 novella** — 🚧 in progress

The biggest single lift on the analysis side.

*Increment 1 shipped:* per-chapter extraction (`roles/chunked_lector.py` + prompt) emitting a `WorldDiff` per chapter, fed the entities-so-far so recurring characters reuse ids; a **deterministic, fully-tested merge** (`worldmerge.merge_world`) that folds the ordered diffs into one `WorldSeed`, with entity resolution by id (primary) and normalized-name backstop, state-evolves-to-latest field rules, and secret/`known_by` accumulation. `analyze()` routes chaptered texts through the chunked path automatically (flat stories keep the whole-text Lector, unchanged); `StoryAnalysis.world_diffs` keeps per-chapter provenance.

*Increment 2 shipped:* the **story-time event log** — `worldlog.build_event_log` derives an ordered `WorldEvent` history from the diffs (character introduced, emotional state changed, secret learned, *in which chapter*), and `worldlog.snapshot_at` materializes the world as of any section. Persisted by `eventstore.py` in **SQLite** (stdlib `sqlite3`, no new dep) as a queryable `world_events` table with a per-section filter — the roadmap's "storage → SQLite" beachhead. `StoryAnalysis.world_events` carries the log. All deterministic and fully tested.

*Increment 3 shipped:* the **chunk-level incremental cache** (`chunkcache.py`, SQLite). Each chapter's `WorldDiff` is cached under a key of *its text + the entities established before it*, so re-analyzing a book re-runs the LLM only on what actually changed: editing the last chapter re-extracts one chapter; editing an early chapter correctly cascades to everything downstream that depends on it. Wired into the `--deep` path (bypassed by `--fresh`). Tested by stubbing the extractor and asserting the exact re-extraction set.

*Increment 4 shipped:* the **entity-resolution eval** (`entity_eval.py`). Labeled mentions (each chapter's extracted character tagged with its true entity) are scored coreference-style — pairwise precision/recall/F1 plus the two interpretable failure counts: **over-merges** (distinct entities wrongly collapsed, e.g. two "John"s) and **missed merges** (same entity left split, e.g. "the old man" ≠ "Silas"). `score_world_diffs` runs it on a real `--deep` run's `world_diffs` against a small name→entity gold, turning "the ids looked consistent" into a number. This is the measurement that makes scaling honest.

*Live-validated:* the first real book-scale run (qwen3.6:35b-mlx on the 5-chapter clockmaker fixture) came back healthy — consistent ids for the main cast, the event log capturing the ch3 secret reveal, the cache at 0.137s on re-run. The eval scored `pair_f1 ≈ 0.85` with the only misses being the "the old man" → Silas coreference case. **`chunked_lector.v2`** attacks exactly that: richer entities-so-far context (archetype + appearance) plus an explicit epithet-resolution rule; re-running the eval measures whether F1 climbs.

*Still open in S1:* op-based *mutations* (removes/moves/field-ops) beyond introduce/state-change/learn; **materialized-state views** over the event table; and continuing to close the **coreference** gap (v2 is the first attempt, measured by the eval). The deterministic backbone of S1 is complete and live-validated; remaining work is LLM-side quality, driven by the eval.

- **Chunked Lector:** per-chapter extraction emitting typed **diffs** (entities added/changed, relationships, secrets, events) rather than one whole-book dump.
- **Diff-merge + entity resolution:** coalesce per-chapter diffs into a global graph; resolve coreference ("the old man" = "Silas") across chapters.
- **Event-sourced world:** a story-time event log with materialized snapshots (who knows what, when; entrances/exits/renames).
- **Windowed style + multi-scale arc:** actually computed per chapter and aggregated, replacing single-profile / single-curve.
- **Storage → SQLite:** event-log table + materialized views; chunk-level incremental cache (re-analyze only changed chapters).
- **Exit:** deconstruct a ~30k-word chaptered novella into a coherent hierarchical `StoryAnalysis`; entity-resolution accuracy measured on a small labeled sample.

### Phase S2 — Retrieval + consistency generation *(Endless)* → **R3 novella→short novel**

The generation side catches up to the same structures.

- **Hierarchical planner:** top-down — macro-outline → chapter outlines → per-chapter beats, each a bounded call.
- **Retrieval-fed Author:** graph queries + a vector index over prior scenes supply per-beat context, superseding the pure rolling synopsis.
- **Editor role (now mandatory):** consistency check against the graph with regen on contradiction — the deferred role becomes load-bearing.
- **Shared graph:** Endless writes to the same event-sourced graph the analyzer reads/produces.
- **Exit:** generate a ~30k-word novella that holds together — a full read-through / Editor pass with no continuity breaks.

### Phase S3 — Book-scale round-trip & transposition *(both)*

Make the loop's critics and transforms work at scale.

- **Hierarchical `compare()`:** arc similarity per level, per-chapter beat alignment, entity-mapping-aware world overlap — so fidelity still means something over a book.
- **Persistent mapping table:** transposition keeps a global, stable entity map so the same character reskins/renames identically in *every* chapter (today's deterministic `--rename` is the seed).
- **Cost controls:** per-role model tiers (cheap for extraction, strong for authoring), safe parallelism across independent chunks, aggressive chunk caching.
- **Exit:** full round-trip on a novella (analyze → transpose → generate → re-analyze → compare) yielding a meaningful hierarchical fidelity score.

### Phase S4 — Scale-up & hardening → **R4 full novel**

- Push chunk counts to full-novel scale; tune retrieval recall/precision and parallelism.
- **Hierarchical eval:** sampling-based human-in-the-loop + automated per-chapter checks (whole-book human eval doesn't scale).
- SQLite performance, incremental everything, resumability across a multi-hour run.
- **Exit:** a full ~100k-word novel processed end to end within a practical time and cost budget.

---

## Dependency order

```
S0 (nest structures, shared)
      │
      ├────────────▶ S1 (chunked analysis + graph, Analyzer)
      │                     │
      └────────────▶ S2 (retrieval + Editor, Endless)
                            │
                     S3 (hierarchical compare + transposition mapping)
                            │
                     S4 (scale-up + hardening)
```

S0 gates everything. S1 and S2 can proceed in parallel once S0 lands (they share the graph contract). S3 needs both. S4 is hardening on top.

---

## The genuinely hard problems (watch these)

1. **Entity resolution across chunks** — the core NLP difficulty of book-scale analysis; quality-defining and error-prone. (S1)
2. **Consistency over hundreds of pages** — why the Editor exists; hard to make reliable. (S2)
3. **Evaluation at length** — `compare()` must go hierarchical; human eval doesn't scale. (S3–S4)
4. **Transposition consistency** — one global, stable mapping or the retelling fractures. (S3)
5. **Cost & latency** — hundreds of beats × roles = hours and real money per book. (S3–S4)

---

## What's reused, not reinvented

Book scale is largely *finishing the roadmap both design docs already sketch*:

- **Endless:** the knowledge graph, Lector-emits-diffs, Editor consistency check, and SQLite event-log are its stated v1/v2 (design §4, §5.3, §9). The rolling synopsis, checkpointing, and per-beat generation are the seeds of context management and resumability.
- **Analyzer:** act hierarchy and structural-template classification (§8.2), the content-addressed store (§4.2, → chunk-level), the fidelity critic (§8.5, → hierarchical), and transposition's deterministic rename enforcement (§8.7, → global mapping table).
- The **shared four-schema contract** and the **determinism boundary** mean these changes are additive on both sides.

**Realistic first target when the time comes:** not *War and Peace* — a **novella (~20–40k words) with explicit chapter markers** (Phase S0→S2). It forces chunking, merge, hierarchy, and the event-sourced graph without the full entity-resolution nightmare of a 400-page cast, and it's the smallest artifact that proves the whole architecture.

---

## Extending the Roadmap: Asset Libraries, Tropes, and Style Aggregation (v1.1 additions)

Our recent implementation of the **Asset Library, Genre Classification, Trope Taxonomies, and Corpus Aggregation** introduces new pathways for scaling to book length:

### 1. Tropes as Graph State Transformers (Phase S1 / S2)
- Today, tropes (e.g., `betrayal`, `faustian_bargain`) are flat annotations on beats. 
- **Scale Reframe:** Tropes should act as state transition templates for the event-sourced world graph. 
  - *Example:* Selecting a `betrayal` trope for a beat automatically triggers a graph update: mutating the relationship status between Character A and Character B to "hostile", creating a new `Secret` node, and modifying their wants/emotional states.

### 2. Genre-Specific Influence Constraints & Warnings (Phase S2)
- Today, mismatched genres trigger warnings (e.g., Gothic style vs Whimsical world).
- **Scale Reframe:** The system should dynamically "blend" conflicting styles or world seeds rather than just warning. If a user forces a Gothic world with a Whimsical style, the orchestrator should inject specific blending directives into the Author prompt (e.g., *"Write in a whimsical register but overlay gothic descriptions of the environment"*).

### 3. Dynamic Style Steering via Corpus Aggregates (Phase S2 / S3)
- Today, we build a static composite profile for an author (e.g. Poe) by averaging metrics across a corpus.
- **Scale Reframe:** Instead of a single static style, use the corpus metrics to *dynamically steer* scenes during book generation. As the book proceeds along the multi-scale arc (e.g., approaching the "worst moment" or climax), the style should dynamically shift to the author's most intense writing style (e.g., higher modifier density, shorter sentence length mean) derived from the climax sections of the source corpus.

### 4. Recombination Playground & CLI Steerability (Phase S0 / S2)
- Expose direct CLI arguments in Endless to override styles, worlds, and templates directly (`--style`, --world-seed, `--beat-template`). This allows rapid, programmatic testing of book-scale recombination recipes without having to constantly edit `config.yaml` or write template files.

