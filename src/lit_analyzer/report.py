"""Render a StoryAnalysis (or a Divergence) as human-readable Markdown.

The report is the legible face of a deconstruction: everything the analyzer
recovered, in one document a person can read (and Mermaid diagrams a GitHub /
Obsidian viewer renders inline). It stays deterministic and dependency-free —
diagrams are just fenced ```mermaid blocks of text, no rendering library.
"""

from __future__ import annotations

import re

from .schemas import Divergence, Section, StoryAnalysis, WorldEvent

_SPARK = "▁▂▃▄▅▆▇█"


def _sparkline(valences: list[float]) -> str:
    """ASCII sparkline of the arc, mapping [-1, 1] onto eight block heights."""
    out = []
    for v in valences:
        idx = int(round((v + 1) / 2 * (len(_SPARK) - 1)))
        out.append(_SPARK[max(0, min(len(_SPARK) - 1, idx))])
    return "".join(out)


def _safe_id(raw: str) -> str:
    """A Mermaid-safe node id (alphanumeric + underscore)."""
    return re.sub(r"\W", "_", raw) or "n"


def _mm(text: str) -> str:
    """Sanitize a string for use inside a Mermaid label/entry.

    Quotes, colons and semicolons are structural in several Mermaid grammars
    (timeline entries split on ``:``), so neutralize them rather than risk a
    diagram that won't parse.
    """
    return re.sub(r"[\":;]", " ", text or "").strip()


def _mermaid_arc(valences: list[float], title: str = "Emotional arc") -> list[str]:
    """A Mermaid xychart line of the arc — the sparkline, but rendered."""
    data = ", ".join(f"{v:.2f}" for v in valences)
    return [
        "```mermaid",
        "xychart-beta",
        f'    title "{_mm(title)}"',
        '    y-axis "valence" -1 --> 1',
        f"    line [{data}]",
        "```",
    ]


def _mermaid_section_tree(root: Section) -> list[str]:
    """A Mermaid graph of the structural hierarchy (book → chapters → beats)."""
    edges: list[str] = []

    def walk(node: Section) -> None:
        nid = _safe_id(node.id)
        label = _mm(node.title or node.id)
        edges.append(f'    {nid}["{label}"]')
        for child in node.children:
            edges.append(f"    {nid} --> {_safe_id(child.id)}")
            walk(child)
        for bid in node.beat_ids:
            beat_node = _safe_id(f"beat_{node.id}_{bid}")
            edges.append(f'    {beat_node}(["{_mm(bid)}"])')
            edges.append(f"    {nid} --> {beat_node}")

    walk(root)
    return ["```mermaid", "graph TD", *edges, "```"]


def _mermaid_timeline(events: list[WorldEvent], titles: dict[str, str]) -> list[str]:
    """A Mermaid timeline of the story-time event log, grouped by section."""
    lines = ["```mermaid", "timeline", "    title Story-time event log"]
    current: str | None = None
    for e in events:
        if e.section_id != current:
            current = e.section_id
            lines.append(f"    section {_mm(titles.get(e.section_id, e.section_id))}")
        entry = _mm(e.entity_id)
        if e.note:
            entry += f" ({_mm(e.note)})"
        lines.append(f"        {_mm(e.kind)} : {entry}")
    lines.append("```")
    return lines


def _section_titles(a: StoryAnalysis) -> dict[str, str]:
    """Map section_id → human title, from section_arcs and the structure tree."""
    titles: dict[str, str] = {}
    for sa in a.section_arcs:
        if sa.title:
            titles[sa.section_id] = sa.title

    def walk(node: Section) -> None:
        if node.title:
            titles.setdefault(node.id, node.title)
        for child in node.children:
            walk(child)

    if a.structure is not None:
        walk(a.structure)
    return titles


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
    curve = [s.valence for s in a.shape.curve]
    lines.append("```")
    lines.append(_sparkline(curve))
    lines.append("```")
    lines.append("")
    lines.extend(_mermaid_arc(curve))
    lines.append("")
    lines.append("| shape | distance | confidence |")
    lines.append("|---|---|---|")
    for s in a.shape.ranking:
        mark = " ◀ best" if s.shape == a.shape.best else ""
        lines.append(f"| {s.shape}{mark} | {s.distance:.3f} | {s.confidence:.3f} |")
    lines.append("")

    # S0: per-chapter (multi-scale) arcs, shown only for a chaptered text.
    if getattr(a, "section_arcs", None):
        lines.append("## Structure (per-chapter arc)")
        lines.append("")
        lines.append("| section | title | shape | arc |")
        lines.append("|---|---|---|---|")
        for sa in a.section_arcs:
            spark = _sparkline([s.valence for s in sa.shape.curve])
            lines.append(f"| {sa.section_id} | {sa.title or ''} | {sa.shape.best} | `{spark}` |")
        lines.append("")
        # The hierarchy itself (book → chapters → beats), when it's more than one node.
        if a.structure is not None and a.structure.children:
            lines.append("### Hierarchy")
            lines.append("")
            lines.extend(_mermaid_section_tree(a.structure))
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

    # S1 (book scale): the story-time event log — the world as a history, not a
    # snapshot. Only present for a chunked (chaptered, --deep) analysis.
    if a.world_events:
        titles = _section_titles(a)
        lines.append("## World history (event log)")
        lines.append("")
        lines.extend(_mermaid_timeline(a.world_events, titles))
        lines.append("")
        lines.append("| # | section | event | entity | note |")
        lines.append("|---|---|---|---|---|")
        for e in a.world_events:
            sect = titles.get(e.section_id, e.section_id)
            lines.append(
                f"| {e.seq} | {sect} | {e.kind} | `{e.entity_id}` ({e.entity_kind}) | {e.note or ''} |"
            )
        lines.append("")

    # S1: per-chapter world observations behind the merged world — who each
    # chapter introduced or touched, before resolution folded them together.
    if a.world_diffs:
        titles = _section_titles(a)
        lines.append("## World by chapter")
        lines.append("")
        for d in a.world_diffs:
            sect = titles.get(d.section_id, d.section_id)
            names = [f"`{c.id}`" for c in d.characters]
            roster = ", ".join(names) if names else "—"
            lines.append(f"- **{sect}** — characters: {roster}")
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
    if div.hierarchy is not None:
        h = div.hierarchy
        # The hierarchy's headline is pacing (reword-robust); per-chapter arc is a
        # diagnostic shown below, not folded into overall (see compare()).
        headline = h.beat_similarity if h.beat_similarity is not None else h.similarity
        lines.append(
            f"| hierarchy (pacing) | {_pct(headline)} | {h.count_a}→{h.count_b} chapters, "
            f"alignment {_pct(h.alignment)}; per-chapter arc is diagnostic |"
        )
    lines.append("")

    # S3: per-chapter fidelity — does the book rise/fall (and pace) alike chapter by chapter?
    if div.hierarchy is not None and div.hierarchy.pairs:
        has_beats = any(p.beat_similarity is not None for p in div.hierarchy.pairs)
        lines.append("## Per-chapter fidelity")
        lines.append("")
        lines.append(
            "> *Arc columns are diagnostic — they localize where chapter arcs move, "
            "but don't count toward overall: a per-chapter sentiment curve is "
            "reword-sensitive, and faithful regeneration rewords by design. "
            "Pacing (beat counts) does count.*"
        )
        lines.append("")
        head = "| # | A | B | shape A → B | arc dist | arc fidelity |"
        sep = "|---|---|---|---|---|---|"
        if has_beats:
            head += " beats A → B | pacing |"
            sep += "---|---|"
        lines.append(head)
        lines.append(sep)
        for p in div.hierarchy.pairs:
            shp = "same" if p.same_best else f"{p.best_a} → {p.best_b}"
            mark = "" if p.similarity >= 0.6 else " ⚠️"
            row = (
                f"| {p.index + 1} | {p.title_a or ''} | {p.title_b or ''} | {shp} | "
                f"{p.curve_distance:.2f} | {_pct(p.similarity)}{mark} |"
            )
            if has_beats:
                bmark = "" if (p.beat_similarity or 0) >= 0.6 else " ⚠️"
                beats = f"{p.beats_a} → {p.beats_b}" if p.beats_a is not None else "—"
                pace = _pct(p.beat_similarity) + bmark if p.beat_similarity is not None else "—"
                row += f" {beats} | {pace} |"
            lines.append(row)
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
