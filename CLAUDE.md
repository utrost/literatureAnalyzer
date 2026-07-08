# CLAUDE.md

Guidance for Claude Code sessions working on this repository.

## What this project is

A personal tool that **deconstructs** human-written stories into structure — the
inverse of the [Endless](https://github.com/utrost/Endless) story engine.
Endless goes structure → prose; this goes prose → structure: emotional arc
(Shape), prose style (StyleProfile), world graph (WorldSeed), and functional
beats (BeatPlan). Single user, single machine, local-first via Ollama — or any
hosted provider (OpenRouter/OpenAI/Anthropic) for the `--deep` passes, key in
`.env`. Phase 0 shipped; book-scale analysis (S1: chunked extraction + world
graph) and the hierarchical round-trip (S3: per-chapter `compare()`, persistent
transposition entity map) are in.

The design doc (`literature_analyzer_design.md`) is the canonical source of
intent and is defined by inversion from Endless — read Endless's
`story_engine_design.md` first. The README documents the actual code surface.

## The contract with Endless (do not break)

`schemas.py` copies four types from Endless verbatim — `Shape`, `StyleProfile`,
`WorldSeed`, `BeatPlan` — so this tool's **output** is Endless's **input**. That
copy is a contract. If you change one of these fields, change it in Endless too,
or the round-trip breaks. The analysis-only types (`ArcSample`, `ShapeMatch`,
`StyleEvidence`, `StoryAnalysis`, plus the S1/S3 additions `Section`, `SectionArc`,
`WorldDiff`, `WorldEvent`, the `Divergence`/`HierarchyDivergence` family, and the
transposition `EntityMap`) are ours to evolve freely.

## Repo layout

```
src/lit_analyzer/
├── cli.py              # Typer entrypoint — `deconstruct <FILE>`
├── analyzer.py         # spine: runs deterministic passes, optional --deep passes
├── segment.py          # words / sentences / paragraphs / windows / chapter_spans (deterministic)
├── structure.py        # Section-tree hierarchy from text (S0, book scale)
├── worldmerge.py       # fold per-chapter WorldDiffs into one world (S1, book scale)
├── worldlog.py         # story-time event log + snapshot materialization (S1)
├── eventstore.py       # SQLite persistence for the event log (S1, stdlib sqlite3)
├── chunkcache.py       # incremental cache: re-extract only changed chapters (S1)
├── entity_eval.py      # entity-resolution eval: labeled mentions → P/R/F1 (S1)
├── sentiment.py        # VADER sentiment (deterministic), lexicon fallback
├── lexicon.py          # tiny built-in sentiment lexicon (bag-of-words fallback)
├── arc.py              # arc sampling + shape classification (deterministic)
├── metrics.py          # prose → StyleProfile (deterministic)
├── compare.py          # fidelity critic: two StoryAnalysis → Divergence, hierarchical per-chapter (§8.5, S3)
├── transform.py        # transposition + persistent EntityMap across chapters (§8.7, S3)
├── bridge.py           # emit an Endless handoff — bundle dir, or one-file --as-doc
├── report.py           # StoryAnalysis / Divergence → Markdown, with Mermaid diagrams
├── config.py           # YAML → Pydantic (only for --deep)
├── store.py            # content-addressed cache for --deep artifacts (§4.2)
├── llm.py              # slim LiteLLM+Instructor wrapper, lazy-imported
├── schemas.py          # shared contract + analysis-only types
├── prompts/*.v1.md     # versioned prompts for the LLM roles
└── roles/              # lector, chunked_lector, beat_labeler, classifier, reskinner, beat_recaster
examples/               # sample stories (public-domain / self-authored)
tests/                  # deterministic-only pytest
config.example.yaml     # canonical default config (--deep only)
```

## Working agreements

**The determinism boundary is the whole design.** Arc + metrics are pure
functions — no model, no network, fully tested. Lector + beat labeler are LLM
calls behind `--deep` and the `deep` optional dependency, lazy-imported. Never
make the deterministic core import litellm/instructor. Keep the base install to
pydantic + typer + pyyaml so tests stay offline and instant.

**Tests.** Deterministic only (no LLM calls). Keep `uv run pytest` green. Add
tests for new code paths. Don't unit-test prompts.

**Prompts are code.** Versioned filenames (`*.v1.md`). Bump to v2 for meaningful
changes.

**Be honest about crudeness.** The sentiment lexicon and several style axes are
proxies (design doc §7). Improve them, but don't oversell them — expose raw
numbers as evidence rather than hiding a guess.

**YAGNI.** Personal project, same as Endless. Three lines beats a framework.

## Pitfalls carried over from Endless (Appendix C there)

1. **`provider: ollama` → `ollama_chat`.** `/api/generate` skips chat templates.
   `llm.py` normalizes it; don't undo.
2. **Local models need `Mode.JSON`, not `Mode.TOOLS`.** Handled in `llm.py` —
   which now auto-picks JSON for Ollama/OpenRouter and tool-calls for
   OpenAI/Anthropic (override per role with `json_mode`).
3. **Set `max_tokens`.** Ollama silently truncates otherwise.
4. **Thinking models burn budget reasoning.** `thinking: false` per role.

## Cloud vs local for `--deep`

The deterministic core needs no model. The `--deep` roles can run on Ollama or a
hosted provider: set the role's `provider` (`openrouter`/`openai`/`anthropic`)
and put the key in `.env` (loaded automatically on the deep path; see
`.env.example`). Handy for modest hardware or faster iteration. The determinism
boundary is unchanged — dotenv/litellm stay lazy behind the deep extra.

## How to verify changes locally

```bash
uv sync
uv run pytest                                        # deterministic tests only
uv run deconstruct examples/the_lantern.txt          # deterministic report (Mermaid arc)
uv run deconstruct examples/the_lantern.txt -f json  # raw StoryAnalysis

# Deep passes (needs the extra + a pulled Ollama model OR a cloud key in .env):
uv sync --extra deep
uv run deconstruct examples/the_clockmaker_of_veil_street.txt --deep   # chaptered → S1 path
```

## Tools and integrations

GitHub MCP tools (prefixed `mcp__github__`) for all GitHub interactions; the
`gh` CLI is NOT available. This repo is scoped to `utrost/literatureAnalyzer`.
