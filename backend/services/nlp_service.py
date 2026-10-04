import spacy
import language_tool_python
import jellyfish
from functools import lru_cache
from pathlib import Path
from wordfreq import zipf_frequency, top_n_list


@lru_cache(maxsize=1)
def get_nlp():
    """Lazy-load spaCy's en_core_web_sm pipeline on first use (B3)."""
    return spacy.load("en_core_web_sm")


@lru_cache(maxsize=1)
def get_tool():
    """Lazy-load LanguageTool on first use (B3)."""
    return language_tool_python.LanguageTool("en-US")


# ---------------------------------------------------------------------------
# English vocabulary for phonetic spell checking (B12)
# ---------------------------------------------------------------------------

VOCAB_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "english_words.txt"
)

DYSLEXIC_WORDLIST = {
    word.strip().lower()
    for word in VOCAB_PATH.read_text(encoding="utf-8").splitlines()
    if word.strip().isalpha()
}


# ---------------------------------------------------------------------------
# Phonetic candidate indexes
# ---------------------------------------------------------------------------

_ZIPF = {}
_BY_FIRST_LETTER = {}
_SOUNDEX_INDEX = {}
_METAPHONE_INDEX = {}


def _add_candidate(word):
    if word in _ZIPF or len(word) < 3 or not word.isalpha():
        return

    freq = zipf_frequency(word, "en")

    if freq < 2.5:
        return

    _ZIPF[word] = freq

    _BY_FIRST_LETTER.setdefault(
        word[0],
        []
    ).append(word)

    _SOUNDEX_INDEX.setdefault(
        jellyfish.soundex(word),
        set()
    ).add(word)

    _METAPHONE_INDEX.setdefault(
        jellyfish.metaphone(word),
        set()
    ).add(word)


# Add words from our local 234k-word vocabulary.
for _w in DYSLEXIC_WORDLIST:
    _add_candidate(_w)


# Add common words / plurals / inflections that may not
# exist in the base vocabulary.
for _w in top_n_list("en", 60000):
    _add_candidate(_w)


_MIN_SCORE = 0.55
_MIN_SCORE_KNOWN_RARE = 0.75

_WEIGHTS = (
    0.30,  # edit similarity
    0.25,  # phonetic similarity
    0.35,  # word frequency
    0.10,  # length similarity
)


_SOUND_RULES = [
    ("gh", "f"),
    ("ph", "f"),
]

_SILENT_START = (
    "kn",
    "wr",
    "gn",
    "ps",
)


def _sound_variants(word):
    """
    Generate spelling variants that represent common
    English sound/spelling relationships.
    """
    variants = {word}

    for old, new in _SOUND_RULES:
        if old in word:
            variants.add(
                word.replace(old, new)
            )

    for pre in _SILENT_START:
        if word.startswith(pre):
            variants.add(word[1:])

    return variants


def _candidates(clean_word, soundex, metaphone):
    """
    Retrieve a manageable set of possible correction candidates.

    Candidates can come from:
    - Soundex matches
    - Metaphone matches
    - Same first letter with similar length
    - Common silent-letter patterns
    """

    candidates = (
        set(_SOUNDEX_INDEX.get(soundex, ()))
        |
        set(_METAPHONE_INDEX.get(metaphone, ()))
    )

    # Same first letter + similar length.
    for word in _BY_FIRST_LETTER.get(
        clean_word[0],
        ()
    ):
        if abs(len(word) - len(clean_word)) <= 3:
            candidates.add(word)

    # Words spelled ph/kn/wr/gn/ps may sound like
    # f/n/r/n/s, so they can belong to another first letter.
    for pre in (
        "ph",
        "kn",
        "wr",
        "gn",
        "ps",
    ):
        for word in _BY_FIRST_LETTER.get(
            pre[0],
            ()
        ):
            if (
                word.startswith(pre)
                and abs(len(word) - len(clean_word)) <= 3
            ):
                candidates.add(word)

    return candidates


def _score(
    clean_word,
    soundex,
    metaphone,
    cand,
):
    """
    Score a candidate using:

    - Edit similarity
    - Phonetic similarity
    - Word frequency
    - Length similarity
    """

    best = 0.0

    w_sim, w_phon, w_freq, w_len = _WEIGHTS

    freq = min(
        _ZIPF[cand],
        8
    ) / 8

    for variant in _sound_variants(cand):

        distance = jellyfish.levenshtein_distance(
            clean_word,
            variant
        )

        longest = max(
            len(clean_word),
            len(variant)
        )

        if distance > max(
            2,
            longest // 2
        ):
            continue

        phon = (
            0.5
            * (
                soundex
                == jellyfish.soundex(variant)
            )
            +
            0.5
            * (
                metaphone
                == jellyfish.metaphone(variant)
            )
        )

        length = (
            1
            -
            abs(
                len(cand)
                -
                len(clean_word)
            )
            /
            max(
                len(clean_word),
                len(cand)
            )
        )

        score = (
            w_sim
            * (
                1
                -
                distance / longest
            )
            +
            w_phon
            * phon
            +
            w_freq
            * freq
            +
            w_len
            * length
        )

        best = max(
            best,
            score
        )

    return best


def _best_suggestion(clean_word):
    """
    Find the highest-scoring phonetic correction.
    """

    soundex = jellyfish.soundex(
        clean_word
    )

    metaphone = jellyfish.metaphone(
        clean_word
    )

    best = None
    best_score = 0.0

    for cand in _candidates(
        clean_word,
        soundex,
        metaphone,
    ):
        if cand == clean_word:
            continue

        score = _score(
            clean_word,
            soundex,
            metaphone,
            cand,
        )

        if score > best_score:
            best = cand
            best_score = score

    return best, best_score


def check_phonetic(text: str) -> list[dict]:
    """
    Phonetic spell correction (B12).

    Uses:
    - Large local English vocabulary
    - Soundex
    - Metaphone
    - Levenshtein distance
    - Word frequency
    - Length similarity
    - Common English sound/spelling rules
    """

    if not text or not text.strip():
        return []

    results = []

    words = text.split()
    search_start=0

    for i, raw_word in enumerate(words):
        position = text.find(raw_word, search_start)
        search_start = position + len(raw_word)
        
        stripped = raw_word.strip(
            ".,!?;:\"'"
        )

        clean_word = stripped.lower()

        if (
            not clean_word
            or not clean_word.isalpha()
        ):
            continue

        # Skip proper nouns / acronyms:
        # capitalised words in the middle of a sentence.
        if (
            i > 0
            and stripped[0].isupper()
            and not words[i - 1].endswith(
                (".", "!", "?")
            )
        ):
            continue

        # Common words are unlikely to be phonetic misspellings.
        if zipf_frequency(
            clean_word,
            "en"
        ) >= 3.0:
            continue

        suggestion, score = _best_suggestion(
            clean_word
        )

        threshold = (
            _MIN_SCORE_KNOWN_RARE
            if clean_word in DYSLEXIC_WORDLIST
            else _MIN_SCORE
        )

        if (
            suggestion
            and score >= threshold
        ):
            results.append({
                "word": raw_word,
                "suggestion": suggestion,
                "position": position,
            })

    return results


# ---------------------------------------------------------------------------
# Homophone detection
# ---------------------------------------------------------------------------

HOMOPHONE_GROUPS = [
    ["there", "their", "they're"],
    ["to", "too", "two"],
    ["write", "right", "rite"],
    ["your", "you're"],
    ["its", "it's"],
    ["whose", "who's"],
    ["here", "hear"],
    ["know", "no"],
    ["break", "brake"],
    ["peace", "piece"],
    ["weather", "whether"],
    ["principal", "principle"],
    ["stationary", "stationery"],
    ["desert", "dessert"],
    ["accept", "except"],
    ["affect", "effect"],
    ["allowed", "aloud"],
    ["board", "bored"],
    ["capital", "capitol"],
    ["cite", "site", "sight"],
    ["complement", "compliment"],
    ["council", "counsel"],
    ["fair", "fare"],
    ["hole", "whole"],
    ["mail", "male"],
    ["meat", "meet"],
    ["passed", "past"],
    ["plain", "plane"],
    ["sea", "see"],
    ["sun", "son"],
    ["tail", "tale"],
    ["wait", "weight"],
    ["weak", "week"],
]


WORD_TO_GROUP = {}

for _group in HOMOPHONE_GROUPS:
    for _word in _group:
        WORD_TO_GROUP[_word] = _group


# Groups with real POS-based disambiguation functions below
_DISAMBIGUATORS = {}


def _disambiguate_there(token):
    """
    their / there / they're.
    """

    if token.dep_ == "expl":
        return "there"

    next_tok = (
        token.doc[token.i + 1]
        if token.i + 1 < len(token.doc)
        else None
    )

    if next_tok is None:
        return token.text.lower()

    if (
        next_tok.pos_ in ("NOUN", "PROPN")
        and next_tok.dep_ != "npadvmod"
    ):
        return "their"

    if next_tok.lemma_ in (
        "be",
        "have",
        "do",
    ):
        return "there"

    if next_tok.pos_ in (
        "VERB",
        "AUX",
    ):
        return "they're"

    return "there"


for _w in [
    "there",
    "their",
    "they're",
]:
    _DISAMBIGUATORS[_w] = _disambiguate_there


def _disambiguate_to(token):
    """
    to / too / two — POS/context rule.
    """

    doc = token.doc

    next_tok = (
        doc[token.i + 1]
        if token.i + 1 < len(doc)
        else None
    )

    next_next_tok = (
        doc[token.i + 2]
        if token.i + 2 < len(doc)
        else None
    )

    word = token.text.lower()

    # too/two at the end of a question:
    # "Who are you talking too?"
    # "Who are you talking two?"
    # should be "to".
    if (
        word in ("too", "two")
        and next_tok is not None
        and next_tok.is_punct
    ):
        sentence_start = token.sent.start

        first_word = doc[
            sentence_start
        ].text.lower()

        if first_word in (
            "who",
            "what",
            "where",
            "when",
            "why",
            "which",
            "whom",
        ):
            return "to"

    # "two" is normally correct when used as a number.
    if token.like_num:
        return "two"

    # "to" tagged as a preposition should remain "to".
    if token.pos_ == "ADP":
        return "to"

    if (
        next_tok is not None
        and next_tok.pos_ == "VERB"
    ):
        return "to"

    if (
        next_tok is not None
        and next_tok.pos_ == "ADJ"
    ):
        if (
            next_next_tok is not None
            and next_next_tok.pos_ in (
                "NOUN",
                "PROPN",
            )
        ):
            return "to"

        return "too"

    if (
        next_tok is not None
        and next_tok.pos_ in (
            "NOUN",
            "PROPN",
            "DET",
            "PRON",
        )
    ):
        return "to"

    if (
        next_tok is None
        or next_tok.is_punct
    ):
        return "too"

    return "to"


for _w in [
    "to",
    "too",
    "two",
]:
    _DISAMBIGUATORS[_w] = _disambiguate_to


def _disambiguate_write(token):
    """
    write / right / rite — POS rule.
    """

    if token.pos_ == "VERB":
        return "write"

    return "right"


for _w in [
    "write",
    "right",
    "rite",
]:
    _DISAMBIGUATORS[_w] = _disambiguate_write


def check_grammar(text: str) -> list[dict]:
    """
    Run text through LanguageTool and return
    a simplified list of grammar issues.
    """

    if not text or not text.strip():
        return []

    matches = get_tool().check(text)

    return [
        {
            "message": match.message,
            "offset": match.offset,
            "length": match.error_length,
            "suggestions": match.replacements[:3],
        }
        for match in matches
    ]


def check_homophones(
    text: str,
    doc: "spacy.tokens.Doc",
) -> list[dict]:
    """
    Homophone detection (F28).

    Walks the spaCy-parsed doc and flags known
    homophone-prone words where we have a
    context-based disambiguation rule.
    """

    if not text or not text.strip():
        return []

    results = []

    for token in doc:

        word_lower = token.text.lower()

        if word_lower not in WORD_TO_GROUP:
            continue

        disambiguator = _DISAMBIGUATORS.get(
            word_lower
        )

        if disambiguator:

            correct_word = disambiguator(
                token
            )

            if correct_word != word_lower:

                results.append({
                    "word": token.text,
                    "suggestion": correct_word,
                    "position": token.idx,
                })

        # Non-disambiguated groups are not automatically
        # flagged because POS alone cannot reliably determine
        # the intended word.


    return results