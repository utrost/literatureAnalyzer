"""Sentiment scoring for the arc sampler.

Primary: VADER (`vaderSentiment`) — a rule-based, deterministic, offline model
whose `compound` score in [-1, 1] handles negation ("no hope"), intensifiers
("utterly ruined"), and punctuation, which the bag-of-words lexicon cannot. This
is the §9 v0.5 "real sentiment model" upgrade; the crude lexicon (`lexicon.py`)
stays as a zero-dependency fallback so the arc pass still runs if VADER is
somehow unavailable, and so its behavior is documented rather than hidden.

Still deterministic and offline — VADER ships its own lexicon; no network, no
model download. It is tuned for short modern text, so it under-reads some
literary-positive phrasing; that's an honest limitation (design doc §7), better
than the negation-blind bag of words it replaces.
"""

from __future__ import annotations

from functools import lru_cache

from . import segment
from .lexicon import polarity


@lru_cache(maxsize=1)
def _analyzer():
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    return SentimentIntensityAnalyzer()


def _lexicon_valence(text: str) -> float:
    """Bag-of-words fallback: mean polarity of the sentiment-bearing words."""
    hits = [p for p in (polarity(t) for t in segment.words(text)) if p != 0]
    return sum(hits) / len(hits) if hits else 0.0


def valence(text: str) -> float:
    """Sentiment of a text span in [-1, 1]. VADER compound, lexicon on failure."""
    try:
        return _analyzer().polarity_scores(text)["compound"]
    except Exception:
        return _lexicon_valence(text)
