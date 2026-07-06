"""Render a StoryAnalysis (or a Divergence) as human-readable Markdown."""

from __future__ import annotations

from .schemas import Divergence, StoryAnalysis

_SPARK = "▁▂▃▄▅▆▇█"


def _sparkline(valences: list[float]) -> str:
    """ASCII sparkline of the arc, mapping [-1, 1] onto eight block heights."""
    out = []
    for v in valences:
        idx = int(round((v + 1) / 2 * (len(_SPARK) - 1)))
        out.append(_SPARK[max(0, min(len(_SPARK) - 1, idx))])
    return "".join(out)


def render(analysis: StoryAnalysis) -> str:
    a = analysis
    lines: list[str] = []
    lines.append(f"# Deconstruction: {a.source}")
    lines.append("")
    lines.append(f"- **Words:** {a.word_count}")
    lines.append(f"- **Shape:** {a.shape.best}")
    if getattr(a, "classification", None) is not None:
        lines.append(f"- **Genre:** {', '.join(a.classification.genre)}")
        lines.append(f"- **Structural Template:** {a.classification.structural_template}")
    lines.append("")

    lines.append("## Emotional arc")
    lines.append("")
    lines.append("```")
    lines.append(_sparkline([s.valence for s in a.shape.curve]))
    lines.append("```")
    lines.append("")
    lines.append("| shape | distance | confidence |")
    lines.append("|---|---|---|")
    for s in a.shape.ranking:
        mark = " ◀ best" if s.shape == a.shape.best else ""
        lines.append(f"| {s.shape}{mark} | {s.distance:.3f} | {s.confidence:.3f} |")
    lines.append("")

    ax = a.style.axes
    lines.append("## Style")
    lines.append("")
    lines.append(f"> {a.style.authored_brief}")
    lines.append("")
    lines.append("| axis | value |")
    lines.append("|---|---|")
    lines.append(f"| sentence length (mean) | {ax.sentence_length_mean} |")
    lines.append(f"| length variance | {ax.sentence_length_variance} |")
    lines.append(f"| diction register | {ax.diction_register} |")
    lines.append(f"| latinate ratio | {ax.latinate_ratio} |")
    lines.append(f"| psychic distance | {ax.psychic_distance} |")
    lines.append(f"| show/tell ratio | {ax.show_tell_ratio} |")
    lines.append(f"| description density | {ax.description_density} |")
    lines.append(f"| dialogue attribution | {ax.dialogue_attribution} |")
    lines.append("")

    if a.world is not None:
        lines.append("## World")
        lines.append("")
        lines.append(f"Protagonist: `{a.world.protagonist_id}`")
        lines.append("")
        for c in a.world.characters:
            star = " ⭐" if c.id == a.world.protagonist_id else ""
            arch = f" ({c.archetype})" if c.archetype else ""
            lines.append(f"- **{c.name}**{star} (`{c.id}`){arch} — wants: {c.wants}; state: {c.emotional_state}")
        if a.world.locations:
            lines.append("")
            lines.append("Locations: " + ", ".join(loc.name for loc in a.world.locations))
        if a.world.chekhov_objects:
            lines.append("Chekhov objects: " + ", ".join(o.name for o in a.world.chekhov_objects))
        lines.append("")

    if a.beats is not None:
        lines.append("## Beats")
        lines.append("")
        for b in a.beats.beats:
            lines.append(f"### {b.id} — {b.shape_function}")
            tropes_str = f" · Tropes: {', '.join(f'`{t}`' for t in b.tropes)}" if b.tropes else ""
            lines.append(f"*{b.mood}* · POV: {b.pov} · ~{b.target_words} words{tropes_str}")
            lines.append("")
            for ev in b.required_events:
                lines.append(f"- {ev}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def render_divergence(div: Divergence) -> str:
    """Render a round-trip Divergence as a Markdown fidelity report."""
    lines: list[str] = []
    lines.append("# Round-trip fidelity")
    lines.append("")
    lines.append(f"- **A:** {div.source_a}")
    lines.append(f"- **B:** {div.source_b}")
    lines.append(f"- **Overall structural fidelity:** {_pct(div.overall)}")
    lines.append("")
    lines.append("| dimension | fidelity | detail |")
    lines.append("|---|---|---|")
    s = div.shape
    same = "same shape" if s.same_best else f"{s.best_a} → {s.best_b}"
    lines.append(f"| shape | {_pct(s.similarity)} | {same}, arc dist {s.curve_distance:.2f} |")
    lines.append(f"| style | {_pct(div.style.similarity)} | {len(div.style.axes)} axes compared |")
    if div.world is not None:
        w = div.world
        prot = "protagonist kept" if w.protagonist_match else "protagonist changed"
        lines.append(
            f"| world | {_pct(w.similarity)} | {prot}; "
            f"chars {w.characters_a}→{w.characters_b}, overlap {_pct(w.character_overlap)} |"
        )
    if div.beats is not None:
        b = div.beats
        lines.append(
            f"| beats | {_pct(b.similarity)} | {b.count_a}→{b.count_b} beats, id overlap {_pct(b.id_overlap)} |"
        )
    lines.append("")

    lines.append("## Style axes")
    lines.append("")
    lines.append("| axis | A | B | Δ |")
    lines.append("|---|---|---|---|")
    for d in div.style.axes:
        mark = "" if d.distance == 0 else (" ⚠️" if d.distance >= 0.5 else "")
        lines.append(f"| {d.axis} | {d.a} | {d.b} | {d.distance:.2f}{mark} |")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"
