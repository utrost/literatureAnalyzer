"""Arc measurement and shape classification — deterministic.

The inverse of Endless's shape *selector*: instead of picking an arc to write
toward, we measure the arc a finished story already has and match it against
the Reagan six. Sentiment is sampled across word-balanced windows (`segment`),
smoothed, normalized, then compared to each reference curve.

Reference valences are identical to Endless's shape library so the two projects
classify against the same vocabulary — a story classified "cinderella" here can
be regenerated with `shape: cinderella` there.
"""

from __future__ import annotations

import math

from . import segment
from .lexicon import polarity
from .schemas import ArcSample, ShapeMatch, ShapeScore

# name -> beat valences (from Endless's data/shapes/*.yaml). Contract-shared.
REFERENCE_SHAPES: dict[str, list[float]] = {
    "man_in_hole": [0.5, -0.3, -0.8, 0.2, 0.7],
    "cinderella": [-0.2, 0.5, -0.5, 0.3, 0.8],
    "tragedy": [0.6, -0.1, -0.4, -0.7, -0.9],
    "rags_to_riches": [-0.6, -0.2, 0.2, 0.5, 0.9],
    "icarus": [-0.1, 0.4, 0.8, -0.3, -0.8],
    "oedipus": [0.3, -0.4, 0.2, -0.5, -0.9],
}

DEFAULT_SEGMENTS = 12


def _raw_valences(text: str, n: int) -> list[float]:
    """Mean word polarity per window, in [-1, 1] before smoothing."""
    vals: list[float] = []
    for win in segment.windows(text, n):
        toks = segment.words(win)
        scores = [polarity(t) for t in toks]
        hits = [s for s in scores if s != 0]
        vals.append(sum(hits) / len(hits) if hits else 0.0)
    return vals


def _smooth(vals: list[float]) -> list[float]:
    """3-point moving average. Tames single-window spikes without erasing turns."""
    if len(vals) < 3:
        return vals
    out = [vals[0]]
    for i in range(1, len(vals) - 1):
        out.append((vals[i - 1] + vals[i] + vals[i + 1]) / 3)
    out.append(vals[-1])
    return out


def _resample(curve: list[float], n: int) -> list[float]:
    """Linearly resample ``curve`` to exactly ``n`` points."""
    if n == 1:
        return [sum(curve) / len(curve)]
    if len(curve) == 1:
        return [curve[0]] * n
    out: list[float] = []
    for i in range(n):
        pos = i * (len(curve) - 1) / (n - 1)
        lo = int(math.floor(pos))
        hi = min(lo + 1, len(curve) - 1)
        frac = pos - lo
        out.append(curve[lo] * (1 - frac) + curve[hi] * frac)
    return out


def _zscore(curve: list[float]) -> list[float]:
    """Center and scale to unit stdev so we compare *shape*, not amplitude."""
    mean = sum(curve) / len(curve)
    var = sum((v - mean) ** 2 for v in curve) / len(curve)
    std = math.sqrt(var)
    if std == 0:
        return [0.0] * len(curve)
    return [(v - mean) / std for v in curve]


def _distance(a: list[float], b: list[float]) -> float:
    """RMSE between two equal-length z-scored curves."""
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)) / len(a))


def classify(text: str, *, segments: int = DEFAULT_SEGMENTS) -> ShapeMatch:
    """Measure the arc and rank the reference shapes by fit."""
    raw = _raw_valences(text, segments)
    if not raw:
        raw = [0.0]
    smoothed = _smooth(raw)
    n = len(smoothed)

    samples = [
        ArcSample(
            index=i,
            position=(i / (n - 1)) if n > 1 else 0.0,
            valence=max(-1.0, min(1.0, v)),
        )
        for i, v in enumerate(smoothed)
    ]

    story_z = _zscore(smoothed)
    scores: list[ShapeScore] = []
    for name, ref in REFERENCE_SHAPES.items():
        ref_z = _zscore(_resample(ref, n))
        dist = _distance(story_z, ref_z)
        scores.append(
            ShapeScore(shape=name, distance=round(dist, 4), confidence=round(1.0 / (1.0 + dist), 4))
        )
    scores.sort(key=lambda s: s.distance)

    return ShapeMatch(best=scores[0].shape, curve=samples, ranking=scores)
