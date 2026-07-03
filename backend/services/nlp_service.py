"""
NLP Service — Owner: M2
Handles grammar correction (F27), phonetic spell correction (F26),
and homophone detection (F28).

STATUS:
- Grammar correction (F27): IMPLEMENTED (Task 2)
- Phonetic spell correction (F26): NOT YET IMPLEMENTED (Task 3)
- Homophone detection (F28): NOT YET IMPLEMENTED (Task 4)
"""

import language_tool_python

# Loaded ONCE at module import time — NOT per-request.
# Costs 10-15s to start (spins up a local Java process under the hood).
# That cost is paid once per server start/reload, never per API call.
# Do NOT move this line inside check_grammar().
tool = language_tool_python.LanguageTool('en-US')


def check_grammar(text: str) -> list[dict]:
    """
    Run text through LanguageTool and return a simplified list of
    grammar issues.

    Each issue dict includes:
      - message: human-readable explanation of the error
      - offset: character index where the error starts
      - length: how many characters the error spans
      - suggestions: up to 3 replacement suggestions

    Returns an empty list for empty/whitespace-only text.
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
    Phonetic spell correction (F26) — jellyfish soundex/metaphone
    vs. dyslexic wordlist.
    NOT YET IMPLEMENTED — placeholder so /nlp/check's response
    shape is already stable. Built in Task 3.
    """
    return []


def check_homophones(text: str) -> list[dict]:
    """
    Homophone detection (F28) — spaCy POS context + homophone map.
    NOT YET IMPLEMENTED — placeholder so /nlp/check's response
    shape is already stable. Built in Task 4.
    """
    return []