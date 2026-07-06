"""Prose style metrics — deterministic.

The inverse of Endless's Author: instead of writing prose *from* a StyleProfile,
we measure prose *into* one. Every axis here is a transparent, dependency-free
proxy — sentence lengths, modifier density, Latinate suffixes, pronoun mix.
Some axes (diction register, psychic distance) are genuinely hard to nail
deterministically; those get honest heuristic defaults, and the raw numbers are
returned as StyleEvidence so nothing is hidden. A richer, LLM-authored style
brief is the `--deep` refinement (see the design doc).
"""

from __future__ import annotations

import math
import re

from . import segment
from .schemas import StyleAxes, StyleEvidence, StyleProfile

_DIALOGUE_RE = re.compile(r"[\"“”‘’']([^\"“”]+)[\"“”‘’']")
_LATINATE_SUFFIX = re.compile(r"(tion|sion|ment|ance|ence|ity|ous|ize|ise|ate|ical|ational)$")
_MODIFIER_LY = re.compile(r"ly$")
_CONTRACTION_RE = re.compile(r"\b\w+'(s|t|re|ve|ll|d|m)\b", re.IGNORECASE)

_FIRST_PERSON = {"i", "me", "my", "mine", "myself", "we", "us", "our", "ours"}
_THIRD_PERSON = {"he", "she", "him", "her", "his", "hers", "they", "them", "their"}
# Rough "telling" markers — naming an interior state outright.
_TELL_WORDS = {
    "felt", "feel", "feeling", "knew", "realized", "thought", "wondered",
    "wanted", "hoped", "feared", "loved", "hated", "believed", "understood",
}


def _bucket(value: float, low: float, high: float) -> str:
    if value < low:
        return "low"
    if value > high:
        return "high"
    return "medium"


def measure(text: str) -> tuple[StyleProfile, StyleEvidence]:
    """Measure prose into a StyleProfile plus the raw evidence behind it."""
    toks = [w.lower() for w in segment.words(text)]
    sents = segment.sentences(text)
    word_count = len(toks) or 1
    sent_count = len(sents) or 1

    sent_lengths = [len(segment.words(s)) for s in sents] or [0]
    mean_len = sum(sent_lengths) / len(sent_lengths)
    var = sum((n - mean_len) ** 2 for n in sent_lengths) / len(sent_lengths)
    stdev = math.sqrt(var)

    dialogue_words = sum(len(segment.words(m)) for m in _DIALOGUE_RE.findall(text))
    dialogue_ratio = dialogue_words / word_count

    modifier_ratio = sum(1 for w in toks if _MODIFIER_LY.search(w)) / word_count
    latinate_ratio = sum(1 for w in toks if _LATINATE_SUFFIX.search(w)) / word_count
    first_person = sum(1 for w in toks if w in _FIRST_PERSON)
    third_person = sum(1 for w in toks if w in _THIRD_PERSON)
    first_person_ratio = first_person / word_count
    contractions = len(_CONTRACTION_RE.findall(text))
    tell_hits = sum(1 for w in toks if w in _TELL_WORDS) / word_count

    # --- map measurements onto the shared StyleAxes vocabulary ---------------
    variance_bucket = _bucket(stdev / max(mean_len, 1), 0.35, 0.7)
    latinate_bucket = _bucket(latinate_ratio, 0.03, 0.07)
    # description_density uses its own vocabulary (sparse/medium/lush).
    _density = _bucket(modifier_ratio, 0.02, 0.045)
    density_bucket = {"low": "sparse", "medium": "medium", "high": "lush"}[_density]

    # POV proxy: first-person-dominant prose reads as close; otherwise medium.
    # "far" (distant summary narration) isn't reliably detectable from pronoun
    # counts alone, so we don't claim it — honest over a guess (design doc §7).
    psychic_distance = "close" if first_person > third_person else "medium"

    # Register: contractions + low Latinate -> colloquial; the opposite -> formal.
    if contractions > word_count * 0.01 and latinate_bucket == "low":
        diction = "colloquial"
    elif latinate_bucket == "high" and contractions == 0:
        diction = "formal"
    else:
        diction = "colloquial"

    # show/tell: fewer interior-state verbs -> more showing. Invert the rate.
    show_tell_ratio = max(0.0, min(1.0, 1.0 - tell_hits * 12))

    # attribution: proxy off how much of the prose is dialogue.
    if dialogue_ratio < 0.1:
        attribution = "minimal"
    elif dialogue_ratio > 0.35:
        attribution = "elaborate"
    else:
        attribution = "conventional"

    axes = StyleAxes(
        sentence_length_mean=int(round(mean_len)),
        sentence_length_variance=variance_bucket,
        diction_register=diction,
        latinate_ratio=latinate_bucket,
        psychic_distance=psychic_distance,
        show_tell_ratio=round(show_tell_ratio, 2),
        description_density=density_bucket,
        dialogue_attribution=attribution,
    )

    profile = StyleProfile(
        id="style_measured",
        name="measured",
        axes=axes,
        authored_brief=_brief(axes),
        exemplars=_exemplars(text),
    )
    evidence = StyleEvidence(
        sentence_count=sent_count,
        word_count=word_count,
        sentence_length_mean=round(mean_len, 2),
        sentence_length_stdev=round(stdev, 2),
        dialogue_word_ratio=round(dialogue_ratio, 4),
        modifier_ratio=round(modifier_ratio, 4),
        latinate_ratio=round(latinate_ratio, 4),
        first_person_ratio=round(first_person_ratio, 4),
    )
    return profile, evidence


def _brief(axes: StyleAxes) -> str:
    """A plain-language brief templated from the measured axes.

    Deterministic and unglamorous by design; `--deep` can author a richer one.
    """
    return (
        f"Sentences average about {axes.sentence_length_mean} words with "
        f"{axes.sentence_length_variance} length variance. Diction is "
        f"{axes.diction_register} with {axes.latinate_ratio} Latinate density and "
        f"{axes.description_density} use of modifiers. Narration sits at "
        f"{axes.psychic_distance} psychic distance and leans "
        f"{'toward showing' if axes.show_tell_ratio >= 0.5 else 'toward telling'} "
        f"(show/tell {axes.show_tell_ratio:.2f}). Dialogue attribution reads as "
        f"{axes.dialogue_attribution}."
    )


def _exemplars(text: str, k: int = 2) -> list[str]:
    """First and last non-trivial paragraphs as voice exemplars for Endless."""
    paras = [p for p in segment.paragraphs(text) if len(segment.words(p)) >= 20]
    if not paras:
        return []
    if len(paras) == 1:
        return paras[:1]
    return [paras[0], paras[-1]][:k]
