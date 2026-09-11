"""
backend/services/syllables.py
Shared syllable counting: NLTK CMU Pronouncing Dictionary first, vowel-group
heuristic when the word is absent. Used by /reading/define and the
complexity / reading-level metrics. The CMU dict loads on first use so it
doesn't slow backend startup.
"""

import re
from functools import lru_cache

import nltk


@lru_cache(maxsize=1)
def _cmu():
    from nltk.corpus import cmudict
    try:
        return cmudict.dict()
    except LookupError:
        nltk.download("cmudict", quiet=True)
        return cmudict.dict()


def _syllables_cmu(word: str):
    """Return syllable count from CMU dict, or None if word not found."""
    pronunciations = _cmu().get(word)
    if not pronunciations:
        return None
    # Each phoneme that ends with a digit represents a vowel nucleus
    return sum(1 for phoneme in pronunciations[0] if phoneme[-1].isdigit())


def _syllables_vowel(word: str) -> int:
    """Fallback heuristic: count vowel groups."""
    count = len(re.findall(r'[aeiouy]+', word))
    # silent-e adjustment
    if word.endswith('e') and count > 1:
        count -= 1
    return max(1, count)


def count_syllables(word: str) -> int:
    """Accurate syllable count: CMU dict first, vowel fallback second.
    Punctuation is ignored ("sunlight," → "sunlight"); returns 0 for
    tokens with no letters."""
    word = re.sub(r"[^a-z']", "", word.lower()).strip("'")
    if not word:
        return 0
    cmu_count = _syllables_cmu(word)
    if cmu_count is not None:
        return cmu_count
    return _syllables_vowel(word)
