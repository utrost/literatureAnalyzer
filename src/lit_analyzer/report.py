"""Render a StoryAnalysis as a human-readable Markdown report."""

from __future__ import annotations

from .schemas import StoryAnalysis

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
            lines.append(f"- **{c.name}**{star} (`{c.id}`) — wants: {c.wants}; state: {c.emotional_state}")
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
            lines.append(f"*{b.mood}* · POV: {b.pov} · ~{b.target_words} words")
            lines.append("")
            for ev in b.required_events:
                lines.append(f"- {ev}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
