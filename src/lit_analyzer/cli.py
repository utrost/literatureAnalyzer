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
    config_path: Path = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config.yaml (only used with --deep).",
    ),
) -> None:
    """Deconstruct a human-written story into shape, style, world, and beats."""
    text = file.read_text()

    deep_config = None
    if deep:
        from .config import default_config_path, load_config

        cfg = load_config(config_path or default_config_path())
        deep_config = cfg.deep

    analysis = analyzer.analyze(
        text,
        source=str(file),
        segments=segments,
        deep_config=deep_config,
    )

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


def main() -> None:
    typer.run(_deconstruct)


if __name__ == "__main__":
    main()
