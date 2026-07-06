"""Entity-resolution eval (S1, book scale).

Measures how well cross-chapter entity resolution works — the make-or-break of
chunked book analysis. Given labeled *mentions* (each chapter's extracted
character, tagged with the true entity it refers to), it scores the resolution
`worldmerge` induces against that gold, coreference-style: pairwise precision /
recall / F1, plus the two interpretable failure counts —

- **over-merges** (false positives): two mentions of *different* entities that
  resolution wrongly collapsed (e.g. two "John"s merged by the name backstop).
- **missed merges** (false negatives): two mentions of the *same* entity left
  separate (the model minted a fresh id and the name didn't match).

Run it on a real `--deep` book's `world_diffs` plus a small hand-written
name→entity gold (`score_world_diffs`) to turn "the ids looked consistent" into a
number. Deterministic and offline.
"""

from __future__ import annotations

from itertools import combinations

from pydantic import BaseModel, Field

from . import worldmerge
from .schemas import Character, WorldDiff


class Mention(BaseModel):
    section_id: str
    char_id: str = Field(description="Id the extractor assigned this mention, in this chapter.")
    name: str
    gold_id: str = Field(description="The true entity this mention refers to.")


class ResolutionScore(BaseModel):
    mentions: int
    gold_entities: int
    predicted_entities: int
    pair_precision: float
    pair_recall: float
    pair_f1: float
    over_merges: int
    missed_merges: int


def _diffs_from_mentions(mentions: list[Mention]) -> list[WorldDiff]:
    by_section: dict[str, list[Character]] = {}
    for m in mentions:
        by_section.setdefault(m.section_id, []).append(
            Character(id=m.char_id, name=m.name, appearance="", wants="", emotional_state="")
        )
    return [WorldDiff(section_id=sid, characters=chars) for sid, chars in by_section.items()]


def score(mentions: list[Mention]) -> ResolutionScore:
    """Score resolution over labeled mentions (coreference-style pairwise P/R/F1)."""
    mapping = worldmerge.resolution_map(_diffs_from_mentions(mentions))
    predicted = [mapping[(m.section_id, m.char_id)] for m in mentions]
    gold = [m.gold_id for m in mentions]

    tp = fp = fn = 0
    for i, j in combinations(range(len(mentions)), 2):
        same_gold = gold[i] == gold[j]
        same_pred = predicted[i] == predicted[j]
        if same_gold and same_pred:
            tp += 1
        elif same_pred and not same_gold:
            fp += 1
        elif same_gold and not same_pred:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return ResolutionScore(
        mentions=len(mentions),
        gold_entities=len(set(gold)),
        predicted_entities=len(set(predicted)),
        pair_precision=round(precision, 4),
        pair_recall=round(recall, 4),
        pair_f1=round(f1, 4),
        over_merges=fp,
        missed_merges=fn,
    )


def score_world_diffs(diffs: list[WorldDiff], gold_by_name: dict[str, str]) -> ResolutionScore:
    """Score a real run's ``world_diffs`` against a small ``name -> entity`` gold.

    ``gold_by_name`` keys are matched case-insensitively; a character whose name
    isn't in the gold is skipped (label only the ones you care about).
    """
    gold = {k.lower(): v for k, v in gold_by_name.items()}
    mentions = [
        Mention(section_id=d.section_id, char_id=c.id, name=c.name, gold_id=gold[c.name.lower()])
        for d in diffs
        for c in d.characters
        if c.name.lower() in gold
    ]
    return score(mentions)
