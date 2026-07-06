# CLAUDE.md

Guidance for Claude Code sessions working on this repository.

## What this project is

A personal tool that **deconstructs** human-written stories into structure — the
inverse of the [Endless](https://github.com/utrost/Endless) story engine.
Endless goes structure → prose; this goes prose → structure: emotional arc
(Shape), prose style (StyleProfile), world graph (WorldSeed), and functional
beats (BeatPlan). Single user, single machine, local-first. Phase 0 is shipped.

The design doc (`literature_analyzer_design.md`) is the canonical source of
intent and is defined by inversion from Endless — read Endless's
`story_engine_design.md` first. The README documents the actual code surface.

## The contract with Endless (do not break)

`schemas.py` copies four types from Endless verbatim — `Shape`, `StyleProfile`,
`WorldSeed`, `BeatPlan` — so this tool's **output** is Endless's **input**. That
copy is a contract. If you change one of these fields, change it in Endless too,
or the round-trip breaks. The analysis-only types (`ArcSample`, `ShapeMatch`,
`StyleEvidence`, `StoryAnalysis`) are ours to evolve freely.

## Repo layout

```
src/lit_analyzer/
├── cli.py              # Typer entrypoint — `deconstruct <FILE>`
├── analyzer.py         # spine: runs deterministic passes, optional --deep passes
├── segment.py          # words / sentences / paragraphs / windows (deterministic)
├── lexicon.py          # tiny built-in sentiment lexicon (bag-of-words)
├── arc.py              # arc sampling + shape classification (deterministic)
├── metrics.py          # prose → StyleProfile (deterministic)
├── compare.py          # fidelity critic: two StoryAnalysis → Divergence (§8.5)
├── bridge.py           # emit an analysis as an Endless handoff bundle (--emit-endless)
├── report.py           # StoryAnalysis / Divergence → Markdown
├── config.py           # YAML → Pydantic (only for --deep)
├── store.py            # content-addressed cache for --deep artifacts (§4.2)
├── llm.py              # slim LiteLLM+Instructor wrapper, lazy-imported
├── schemas.py          # shared contract + analysis-only types
├── prompts/*.v1.md     # versioned prompts for the LLM roles
└── roles/              # lector.py (world), beat_labeler.py (beats)
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
2. **Local models need `Mode.JSON`, not `Mode.TOOLS`.** Handled in `llm.py`.
3. **Set `max_tokens`.** Ollama silently truncates otherwise.
4. **Thinking models burn budget reasoning.** `thinking: false` per role.

## How to verify changes locally

```bash
uv sync
uv run pytest
uv run deconstruct examples/the_lantern.txt          # deterministic report
uv run deconstruct examples/the_lantern.txt -f json  # raw StoryAnalysis

# Deep passes (needs the extra + a pulled model):
uv sync --extra deep
uv run deconstruct examples/the_lantern.txt --deep
```

## Tools and integrations

GitHub MCP tools (prefixed `mcp__github__`) for all GitHub interactions; the
`gh` CLI is NOT available. This repo is scoped to `utrost/literatureAnalyzer`.
