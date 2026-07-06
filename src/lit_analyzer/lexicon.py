"""A tiny built-in sentiment lexicon.

Reagan et al. (2016) measured emotional arcs with bag-of-words sentiment —
"crude; but it worked" is the note in Endless's design doc, and it's the note
here too. This is a deliberately small, dependency-free polarity list: enough
to trace the *shape* of an arc across a whole story, not to score a single
sentence precisely. Swapping in a real sentiment model (VADER, a lexicon like
NRC, or an LLM pass) is a later-phase refinement — see the design doc.

Words are lemmatized only loosely; the arc sampler also matches common suffix
inflections, so "feared"/"fearing" hit "fear" without listing every form.
"""

from __future__ import annotations

POSITIVE: frozenset[str] = frozenset(
    {
        "good", "great", "happy", "joy", "joyful", "love", "loved", "loving",
        "hope", "hopeful", "warm", "bright", "beautiful", "wonderful", "glad",
        "smile", "smiled", "laugh", "laughed", "laughter", "delight", "pleasure",
        "peace", "peaceful", "calm", "gentle", "kind", "kindness", "safe",
        "win", "won", "victory", "triumph", "succeed", "success", "gain",
        "rich", "wealth", "reward", "gift", "bless", "blessed", "grace",
        "free", "freedom", "light", "dawn", "spring", "bloom", "flourish",
        "friend", "friendship", "comfort", "tender", "sweet", "cheer",
        "brave", "courage", "strong", "strength", "proud", "pride", "honor",
        "wonder", "marvel", "dream", "shine", "glow", "radiant", "thrive",
        "heal", "healed", "rescue", "saved", "relief", "grateful", "content",
        "embrace", "welcome", "celebrate", "festival", "wedding", "reunion",
    }
)

NEGATIVE: frozenset[str] = frozenset(
    {
        "bad", "sad", "sadness", "sorrow", "grief", "pain", "hurt", "ache",
        "fear", "afraid", "terror", "dread", "horror", "panic", "anxious",
        "anger", "angry", "rage", "fury", "hate", "hated", "bitter", "cruel",
        "dark", "darkness", "cold", "bleak", "grim", "gloom", "shadow",
        "lose", "lost", "loss", "fail", "failure", "defeat", "ruin", "ruined",
        "die", "died", "death", "dead", "kill", "killed", "murder", "blood",
        "cry", "cried", "weep", "tears", "wound", "wounded", "broken", "break",
        "alone", "lonely", "abandon", "abandoned", "betray", "betrayal",
        "poor", "poverty", "hunger", "starve", "sick", "illness", "disease",
        "despair", "hopeless", "helpless", "trapped", "prison", "chains",
        "storm", "wreck", "burn", "burned", "fire", "ash", "decay", "rot",
        "war", "battle", "enemy", "threat", "danger", "curse", "cursed",
        "guilt", "shame", "regret", "doom", "fall", "fell", "collapse", "end",
        "empty", "hollow", "silence", "scream", "screamed", "suffer", "torment",
    }
)

# Common inflections we strip before lookup, longest first.
_SUFFIXES = ("ing", "ed", "es", "s")


def polarity(word: str) -> int:
    """Return +1, -1, or 0 for a single lowercase word.

    Tries the word as-is, then with common suffixes stripped, so inflected
    forms match their root without the lexicon listing every variant.
    """
    w = word.lower()
    if w in POSITIVE:
        return 1
    if w in NEGATIVE:
        return -1
    for suf in _SUFFIXES:
        if w.endswith(suf) and len(w) > len(suf) + 2:
            root = w[: -len(suf)]
            if root in POSITIVE:
                return 1
            if root in NEGATIVE:
                return -1
    return 0
