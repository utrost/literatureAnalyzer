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
    as_doc: bool = typer.Option(
        False,
        "--as-doc",
        help="With --emit-endless, write a single self-contained Markdown file (readable dossier + embedded artifacts) instead of a bundle directory. Endless ingests it with --from-doc.",
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
            if as_doc:
                doc = bridge.emit_endless_doc(analysis, emit_endless)
                typer.echo(
                    f"emitted Endless handoff doc → {doc.path} "
                    f"(run {doc.run_id}, style '{doc.style_name}'); "
                    f"ingest with `story --from-doc {doc.path} --skip-preflight`",
                    err=True,
                )
            else:
                result = bridge.emit_endless(analysis, emit_endless)
                typer.echo(
                    f"emitted Endless bundle → {result.dest} "
                    f"(run {result.run_id}, style '{result.style_name}'); see HOWTO.md",
                    err=True,
                )
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2)

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
    cached_classification = None if fresh else store.load_classification()
    cached_beats = None
    if not fresh and meta.get("segments") == segments:
        cached_beats = store.load_beats()

    # Chunk-level incremental cache for the chaptered (S1) extraction path.
    chunk_cache = None
    if not fresh:
        from .chunkcache import ChunkCache

        chunk_cache = ChunkCache.open(store_dir or DEFAULT_STORE_DIR)

    analysis = analyzer.analyze(
        text,
        source=str(file),
        segments=segments,
        deep_config=cfg.deep,
        world=cached_world,
        beats=cached_beats,
        classification=cached_classification,
        chunk_cache=chunk_cache,
    )
    if chunk_cache is not None:
        chunk_cache.close()

    store.save_world(analysis.world)
    store.save_beats(analysis.beats)
    store.save_classification(analysis.classification)
    store.save_analysis(analysis)
    store.write_meta(
        source=str(file),
        text_sha=content_key(text),
        segments=segments,
        shape=analysis.shape.best,
    )

    # Auto-deposit to the library
    from .library import AssetLibrary
    try:
        lib = AssetLibrary.open()
        deposited = lib.deposit_analysis(analysis)
        typer.echo(
            f"Library: auto-deposited assets {list(deposited.keys())} to {lib.root}",
            err=True,
        )
    except Exception as e:
        typer.echo(f"Library warning: failed to auto-deposit assets: {e}", err=True)

    typer.echo(
        f"deep: world={'cached' if cached_world else 'computed'}, "
        f"beats={'cached' if cached_beats else 'computed'}, "
        f"classification={'cached' if cached_classification else 'computed'} "
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


library_app = typer.Typer(name="library", help="Browse and search the asset library.")


@library_app.command(name="list")
def library_list(
    asset_type: str = typer.Option(
        None, "--type", "-t", help="Filter by asset type: style, world, beat_template"
    ),
    genre: str = typer.Option(None, "--genre", "-g", help="Filter by genre"),
    author: str = typer.Option(None, "--author", "-a", help="Filter by author"),
    tag: str = typer.Option(None, "--tag", help="Filter by tag"),
    shape: str = typer.Option(None, "--shape", help="Filter by shape"),
    trope: str = typer.Option(None, "--trope", help="Filter by trope"),
):
    """List assets stored in the library, with optional filtering."""
    from .library import AssetLibrary

    lib = AssetLibrary.open()
    assets = lib.list_assets(
        asset_type=asset_type, genre=genre, author=author, tag=tag, shape=shape, trope=trope
    )
    if not assets:
        typer.echo("No assets found.")
        return
    for a in assets:
        source_info = (
            f" (from '{a.source_story}' by {a.source_author or 'unknown'})"
            if a.source_story
            else ""
        )
        typer.echo(f"[{a.type}] {a.asset_id}{source_info}")


@library_app.command(name="show")
def library_show(
    asset_type: str = typer.Argument(..., help="Asset type: style, world, beat_template"),
    asset_id: str = typer.Argument(..., help="Asset ID"),
):
    """Show details of a specific asset from the library."""
    from .library import AssetLibrary
    import json
    import yaml

    lib = AssetLibrary.open()
    path = lib.asset_path(asset_type, asset_id)
    if not path or not path.exists():
        typer.echo(
            f"Asset '{asset_id}' of type '{asset_type}' not found in library.", err=True
        )
        raise typer.Exit(code=1)
    typer.echo(f"File: {path}\n")
    if path.suffix == ".json":
        typer.echo(json.dumps(json.loads(path.read_text()), indent=2))
    else:
        typer.echo(path.read_text())


@library_app.command(name="search")
def library_search(
    query: str = typer.Argument(..., help="Search query string"),
):
    """Search for assets in the library by query string."""
    from .library import AssetLibrary

    lib = AssetLibrary.open()
    assets = lib.search(query)
    if not assets:
        typer.echo("No matching assets found.")
        return
    for a in assets:
        source_info = (
            f" (from '{a.source_story}' by {a.source_author or 'unknown'})"
            if a.source_story
            else ""
        )
        typer.echo(f"[{a.type}] {a.asset_id}{source_info}")


corpus_app = typer.Typer(name="corpus", help="Analyze and aggregate style across a corpus of texts.")


@corpus_app.command(name="build")
def corpus_build(
    directory: Path = typer.Argument(..., help="Directory containing plain-text files to analyze"),
    author: str = typer.Option(..., "--author", "-a", help="Name of the author"),
):
    """Analyze all text files in a directory and build/deposit a composite author style profile."""
    from .corpus import build_author_profile
    from .library import AssetLibrary

    if not directory.exists() or not directory.is_dir():
        typer.echo(f"Error: directory '{directory}' does not exist or is not a directory.", err=True)
        raise typer.Exit(code=1)

    files = [f for f in directory.iterdir() if f.is_file() and f.suffix in (".txt", ".md")]
    if not files:
        typer.echo(f"No .txt or .md files found in directory '{directory}'.", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Analyzing {len(files)} files in '{directory}' for author '{author}'...", err=True)
    try:
        profile = build_author_profile(files, author_name=author)
        lib = AssetLibrary.open()
        dest = lib.deposit_author_style(profile, author_name=author)
        typer.echo(f"Success! Deposited consolidated author style to: {dest}", err=True)
    except Exception as exc:
        typer.echo(f"Error building author profile: {exc}", err=True)
        raise typer.Exit(code=1)


def main() -> None:
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "library":
        library_app(args=sys.argv[2:])
    elif len(sys.argv) > 1 and sys.argv[1] == "corpus":
        corpus_app(args=sys.argv[2:])
    else:
        typer.run(_deconstruct)


if __name__ == "__main__":
    main()
