"""Typer CLI — `deconstruct <FILE>`.

Single-command app via ``typer.run`` so invocation is just ``deconstruct story.txt``.
The deterministic passes always run; ``--deep`` adds the LLM world/beat extraction.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from . import analyzer, report
from .arc import DEFAULT_SEGMENTS


def _deconstruct(
    file: Path = typer.Argument(..., help="Path to a plain-text story to deconstruct."),
    out: Path = typer.Option(
        None,
        "--out",
        "-o",
        help="Write the report here. Defaults to stdout.",
    ),
    fmt: str = typer.Option(
        "markdown",
        "--format",
        "-f",
        help="Output format: 'markdown' or 'json'.",
    ),
    segments: int = typer.Option(
        DEFAULT_SEGMENTS,
        "--segments",
        help="Number of windows to sample the emotional arc across.",
    ),
    deep: bool = typer.Option(
        False,
        "--deep",
        help="Also run the LLM Lector (world graph) and beat labeler. Needs the 'deep' extra + a configured model.",
    ),
    fresh: bool = typer.Option(
        False,
        "--fresh",
        help="With --deep, ignore any cached world/beats and recompute them.",
    ),
    store_dir: Path = typer.Option(
        None,
        "--store-dir",
        help="Where --deep artifacts are cached. Defaults to out/analyses.",
    ),
    config_path: Path = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config.yaml (only used with --deep).",
    ),
) -> None:
    """Deconstruct a human-written story into shape, style, world, and beats."""
    text = file.read_text()

    if deep:
        analysis = _deep_analyze(
            text, file, segments, fresh, store_dir, config_path
        )
    else:
        # Deterministic passes are instant and offline — no store, no cache.
        analysis = analyzer.analyze(text, source=str(file), segments=segments)

    if fmt == "json":
        rendered = json.dumps(analysis.model_dump(), indent=2)
    elif fmt == "markdown":
        rendered = report.render(analysis)
    else:
        typer.echo(f"unknown format {fmt!r}; use 'markdown' or 'json'", err=True)
        raise typer.Exit(code=2)

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered)
        typer.echo(f"wrote {out} — shape: {analysis.shape.best}")
    else:
        typer.echo(rendered)


def _deep_analyze(
    text: str,
    file: Path,
    segments: int,
    fresh: bool,
    store_dir: Path | None,
    config_path: Path | None,
):
    """Run --deep with the artifact cache: reuse world/beats when possible.

    world depends only on the text (the store key), so it's reused whenever
    present. beats depend on the classified shape, which depends on --segments,
    so they're reused only when the cached run used the same segment count.
    """
    from .config import default_config_path, load_config
    from .store import DEFAULT_STORE_DIR, AnalysisStore, content_key

    cfg = load_config(config_path or default_config_path())
    store = AnalysisStore.open(store_dir or DEFAULT_STORE_DIR, text)
    meta = store.read_meta()

    cached_world = None if fresh else store.load_world()
    cached_beats = None
    if not fresh and meta.get("segments") == segments:
        cached_beats = store.load_beats()

    analysis = analyzer.analyze(
        text,
        source=str(file),
        segments=segments,
        deep_config=cfg.deep,
        world=cached_world,
        beats=cached_beats,
    )

    store.save_world(analysis.world)
    store.save_beats(analysis.beats)
    store.save_analysis(analysis)
    store.write_meta(
        source=str(file),
        text_sha=content_key(text),
        segments=segments,
        shape=analysis.shape.best,
    )

    typer.echo(
        f"deep: world={'cached' if cached_world else 'computed'}, "
        f"beats={'cached' if cached_beats else 'computed'} "
        f"→ {store.root}",
        err=True,
    )
    return analysis


def main() -> None:
    typer.run(_deconstruct)


if __name__ == "__main__":
    main()
