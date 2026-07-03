"""
NLP Service — Owner: M2
Handles grammar correction (F27), phonetic spell correction (F26),
and homophone detection (F28).

STATUS:
- Grammar correction (F27): IMPLEMENTED (Task 2)
- Phonetic spell correction (F26): IMPLEMENTED (Task 3)
- Homophone detection (F28): NOT YET IMPLEMENTED (Task 4)
"""

import language_tool_python
import jellyfish
from wordfreq import zipf_frequency

# Loaded ONCE at module import time — NOT per-request.
# Costs 10-15s to start (spins up a local Java process under the hood).


tool = language_tool_python.LanguageTool('en-US')

# Dyslexic-confusion wordlist. Includes AC-19's required test cases
# (phone, knife, was, they, could) plus common confusions.
DYSLEXIC_WORDLIST = [
    "because", "beautiful", "friend", "people", "there", "their",
    "they're", "they", "were", "where", "which", "witch", "definitely",
    "separate", "different", "necessary", "receive", "believe",
    "though", "through", "thought", "enough", "although",
    "island", "knight", "know", "knew", "write", "right",
    "example", "experience", "environment", "government",
    "restaurant", "library", "February", "Wednesday",
    "phone", "knife", "was", "could", "should", "would",
]

# Precomputed once at module load, not per-request.
_WORDLIST_SOUNDEX = {w: jellyfish.soundex(w) for w in DYSLEXIC_WORDLIST}
_WORDLIST_METAPHONE = {w: jellyfish.metaphone(w) for w in DYSLEXIC_WORDLIST}


def check_grammar(text: str) -> list[dict]:
    """
    Run text through LanguageTool and return a simplified list of
    grammar issues.
    """


    if not text or not text.strip():
        return []

    matches = tool.check(text)

    return [
        {
            "message": match.message,
            "offset": match.offset,
            "length": match.error_length,
            "suggestions": match.replacements[:3],
        }
        for match in matches
    ]


def check_phonetic(text: str) -> list[dict]:
    """
    Phonetic spell correction (F26).

    Uses jellyfish.soundex() and jellyfish.metaphone() against the
    dyslexic wordlist, per PRD spec. Also uses Levenshtein edit
    distance as a ranking/fallback layer, for two reasons found
    during testing:
      1. Soundex/metaphone can both match a misspelling to MULTIPLE
         wordlist words that share the same code (e.g. "wuz" matches
         both "which" and "was" on soundex alone). Edit distance
         picks the genuinely closest one.
      2. Some misspellings drop a real consonant entirely (e.g. "cud"
         vs "could" drops the L) — phonetic codes can't recover a
         sound that isn't there, but edit distance still catches it.
    """
    if not text or not text.strip():
        return []

    results = []
    words = text.split()

    for i, raw_word in enumerate(words):
        clean_word = raw_word.strip(".,!?;:\"'").lower()
        if not clean_word:
            continue

        if clean_word in DYSLEXIC_WORDLIST:
            continue

        if zipf_frequency(clean_word, "en") >= 3.0:
            continue

        word_soundex = jellyfish.soundex(clean_word)
        word_metaphone = jellyfish.metaphone(clean_word)

        candidates = []
        for known_word in DYSLEXIC_WORDLIST:
            soundex_match = word_soundex == _WORDLIST_SOUNDEX[known_word]
            metaphone_match = word_metaphone == _WORDLIST_METAPHONE[known_word]
            distance = jellyfish.levenshtein_distance(clean_word, known_word)

            # Candidate if phonetically flagged OR spelled close enough
            if soundex_match or metaphone_match or distance <= 2:
                candidates.append((distance, known_word))

        if candidates:
            # Best match = smallest edit distance, not first found
            candidates.sort(key=lambda c: c[0])
            best_distance, best_word = candidates[0]
            results.append({
                "word": raw_word,
                "suggestion": best_word,
                "position": i,
            })

    return results


def check_homophones(text: str) -> list[dict]:
    """
    Homophone detection (F28) — spaCy POS context + homophone map.
    NOT YET IMPLEMENTED — placeholder so /nlp/check's response
    shape is already stable. Built in Task 4.
    """
    return []