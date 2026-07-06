"""Corpus aggregation and voice consensus analysis.

Aggregates multiple works by the same author to compute a consensus style profile
representing their overall voice, selecting the most characteristic paragraphs as exemplars.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from . import metrics, segment
from .schemas import StyleAxes, StyleProfile


def build_author_profile(files: list[Path], author_name: str) -> StyleProfile:
    """Analyze multiple files to build a consensus StyleProfile for an author."""
    if not files:
        raise ValueError("No files provided for corpus analysis")

    profiles: list[StyleProfile] = []
    texts: list[str] = []

    for f in files:
        text = f.read_text()
        texts.append(text)
        profile, _ = metrics.measure(text)
        profiles.append(profile)

    # 1. Average numerical dimensions
    avg_len = sum(p.axes.sentence_length_mean for p in profiles) / len(profiles)
    target_mean_len = int(round(avg_len))

    avg_show_tell = sum(p.axes.show_tell_ratio for p in profiles) / len(profiles)
    target_show_tell = round(avg_show_tell, 2)

    # 2. Consensus (mode) for categorical dimensions
    def get_mode(attr: str) -> str:
        vals = [getattr(p.axes, attr) for p in profiles]
        return Counter(vals).most_common(1)[0][0]

    target_variance = get_mode("sentence_length_variance")
    target_diction = get_mode("diction_register")
    target_latinate = get_mode("latinate_ratio")
    target_psychic = get_mode("psychic_distance")
    target_density = get_mode("description_density")
    target_attribution = get_mode("dialogue_attribution")

    target_axes = StyleAxes(
        sentence_length_mean=target_mean_len,
        sentence_length_variance=target_variance,
        diction_register=target_diction,
        latinate_ratio=target_latinate,
        psychic_distance=target_psychic,
        show_tell_ratio=target_show_tell,
        description_density=target_density,
        dialogue_attribution=target_attribution,
    )

    # 3. Scan all paragraphs across the corpus for the most characteristic exemplars
    candidate_paras: list[str] = []
    seen_paras = set()
    for text in texts:
        for p in segment.paragraphs(text):
            p_strip = p.strip()
            # Clean paragraphs containing at least 20 words
            if len(segment.words(p_strip)) >= 20 and p_strip not in seen_paras:
                candidate_paras.append(p_strip)
                seen_paras.add(p_strip)

    # Calculate distance for each candidate
    scored_paras: list[tuple[float, str]] = []
    for p in candidate_paras:
        try:
            p_profile, _ = metrics.measure(p)
            dist = _style_distance(p_profile.axes, target_axes)
            scored_paras.append((dist, p))
        except Exception:
            continue

    # Sort ascending (closest first)
    scored_paras.sort(key=lambda x: x[0])
    # Extract top 3 exemplars
    exemplars = [text for _, text in scored_paras[:3]]

    # Fallback to defaults if no suitable paragraphs found
    if not exemplars:
        exemplars = []
        for p in profiles:
            exemplars.extend(p.exemplars)
        exemplars = list(set(exemplars))[:3]

    from .library import _slug

    author_slug = _slug(author_name)

    return StyleProfile(
        id=f"style_author_{author_slug}",
        name=f"author_{author_slug}",
        axes=target_axes,
        authored_brief=metrics._brief(target_axes),
        exemplars=exemplars,
    )


def _style_distance(axes_p: StyleAxes, target: StyleAxes) -> float:
    """Compute the style distance between a paragraph's axes and target axes."""
    # Sentence length (normalized by target)
    dist = abs(axes_p.sentence_length_mean - target.sentence_length_mean) / max(target.sentence_length_mean, 1)
    # Show/tell ratio
    dist += abs(axes_p.show_tell_ratio - target.show_tell_ratio)

    # Categorical penalties
    categoricals = [
        "sentence_length_variance",
        "diction_register",
        "latinate_ratio",
        "psychic_distance",
        "description_density",
        "dialogue_attribution",
    ]
    for attr in categoricals:
        val_p = getattr(axes_p, attr)
        val_t = getattr(target, attr)
        if val_p != val_t:
            dist += 0.5

    return dist
