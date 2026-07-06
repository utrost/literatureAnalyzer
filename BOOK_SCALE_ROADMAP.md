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

### Phase S0 — Nestable structures *(shared contract)*

The prerequisite everything else depends on. Additive schema work; no scale yet.

- **Shared contract:** nest `BeatPlan` into a tree (`Book → Part → Chapter → Scene → Beat`); a multi-scale `Shape` (arc per level). A flat story becomes a single-node tree — existing flows unchanged.
- **Analyzer:** chapter/scene segmentation (markers + heuristics) feeding the tree; arc sampled per level.
- **Endless:** planner and orchestrator accept the tree (generate a one-node tree exactly as today).
- **Exit:** schemas + segmentation land; all existing R0 tests pass unchanged; a short story round-trips through the tree form.

### Phase S1 — Chunked analysis + world graph *(Analyzer)* → **R2 novella**

The biggest single lift on the analysis side.

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
