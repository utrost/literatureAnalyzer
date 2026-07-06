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
    file: Path = typer.Argument(
        None, help="Path to a plain-text story to deconstruct. Omit when using --from."
    ),
    from_analysis: Path = typer.Option(
        None,
        "--from",
        help="Reload a saved analysis.json instead of analyzing a file. Re-renders without recomputing.",
    ),
    emit_endless: Path = typer.Option(
        None,
        "--emit-endless",
        help="Also write an Endless-consumable handoff bundle (world/beats/style) to this dir. Needs --deep artifacts.",
    ),
    compare_to: Path = typer.Option(
        None,
        "--compare",
        help="Compare this analysis against a saved analysis.json and report round-trip structural fidelity.",
    ),
    transpose_to: str = typer.Option(
        None,
        "--transpose",
        help="Retell the story in this setting brief, e.g. \"cyberpunk generation ship\". Implies --deep; needs a model.",
    ),
    directive: list[str] = typer.Option(
        None,
        "--directive",
        help="Steer the transposition (repeatable): 'age Huck to 40', 'make Tom a woman'.",
    ),
    rename: list[str] = typer.Option(
        None,
        "--rename",
        help="Force an entity's new name (repeatable): 'jim=N-7'. Enforced exactly.",
    ),
    as_style: Path = typer.Option(
        None,
        "--as-style",
        help="Retell in this voice: a StyleProfile or analysis.json (e.g. one extracted from another author).",
    ),
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
    from .schemas import StoryAnalysis

    # Transposing the source needs its world + beats, so it implies --deep.
    deep = deep or transpose_to is not None

    if from_analysis is not None:
        # Reload a saved analysis — no recompute, no model.
        analysis = StoryAnalysis.model_validate_json(from_analysis.read_text())
    elif file is not None:
        text = file.read_text()
        if deep:
            analysis = _deep_analyze(text, file, segments, fresh, store_dir, config_path)
        else:
            # Deterministic passes are instant and offline — no store, no cache.
            analysis = analyzer.analyze(text, source=str(file), segments=segments)
    else:
        typer.echo("provide a FILE to analyze, or --from analysis.json to reload", err=True)
        raise typer.Exit(code=2)

    if transpose_to is not None:
        analysis = _transpose(
            analysis, transpose_to, directive or [], rename or [], as_style, config_path
        )

    if emit_endless is not None:
        from . import bridge

        try:
            result = bridge.emit_endless(analysis, emit_endless)
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2)
        typer.echo(
            f"emitted Endless bundle → {result.dest} "
            f"(run {result.run_id}, style '{result.style_name}'); see HOWTO.md",
            err=True,
        )

    if compare_to is not None:
        # Fidelity critic (§8.5): diff this analysis against a saved one.
        from . import compare, report as _report

        other = StoryAnalysis.model_validate_json(compare_to.read_text())
        divergence = compare.compare(analysis, other)
        rendered = (
            json.dumps(divergence.model_dump(), indent=2)
            if fmt == "json"
            else _report.render_divergence(divergence)
        )
        if out:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(rendered)
            typer.echo(f"wrote {out} — fidelity {divergence.overall:.0%}")
        else:
            typer.echo(rendered)
        return

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


def _load_style(path: Path):
    """Resolve --as-style to a StyleProfile: accept a StyleProfile or an analysis.json."""
    from .schemas import StoryAnalysis, StyleProfile

    raw = path.read_text()
    try:
        return StyleProfile.model_validate_json(raw)
    except Exception:
        return StoryAnalysis.model_validate_json(raw).style


def _transpose(analysis, setting, directives, renames, as_style, config_path):
    """Retell a deconstructed story in a new setting and (optional) voice."""
    from .config import default_config_path, load_config
    from . import transform

    try:
        spec = transform.Transposition(
            setting=setting,
            directives=directives,
            renames=transform.parse_renames(renames),
            style=_load_style(as_style) if as_style else None,
        )
        cfg = load_config(config_path or default_config_path())
        result = transform.transpose(cfg.deep, analysis, spec)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2)

    voice = f", voice '{spec.style.name}'" if spec.style else ""
    typer.echo(f"transposed → {setting}{voice}", err=True)
    return result


def main() -> None:
    typer.run(_deconstruct)


if __name__ == "__main__":
    main()
