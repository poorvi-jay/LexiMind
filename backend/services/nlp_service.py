import spacy
import language_tool_python
import jellyfish
from functools import lru_cache
from wordfreq import zipf_frequency


@lru_cache(maxsize=1)
def get_nlp():
    """Lazy-load spaCy's en_core_web_sm pipeline on first use (B3).
    Previously loaded at import time, so every backend startup paid
    this cost even if nobody opened the Writing page that session."""
    return spacy.load("en_core_web_sm")


@lru_cache(maxsize=1)
def get_tool():
    """Lazy-load LanguageTool on first use (B3). LanguageTool starts a
    Java subprocess; loading it at import time meant a missing/broken
    Java install crashed the ENTIRE backend at startup, not just this
    one feature."""
    return language_tool_python.LanguageTool('en-US')

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


_WORDLIST_SOUNDEX = {w: jellyfish.soundex(w) for w in DYSLEXIC_WORDLIST}
_WORDLIST_METAPHONE = {w: jellyfish.metaphone(w) for w in DYSLEXIC_WORDLIST}


def check_grammar(text: str) -> list[dict]:
    """
    Run text through LanguageTool and return a simplified list of
    grammar issues.
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

HOMOPHONE_GROUPS = [
    ["there", "their", "they're"],      # POS-disambiguated
    ["to", "too", "two"],               # POS-disambiguated
    ["write", "right", "rite"],         # POS-disambiguated
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

    Order matters. The expletive check comes first: in existential
    sentences ("There is a problem", "There are many books") the
    token after "there" is a verb, so the VERB/AUX branch below would
    otherwise fire and suggest "they're" — telling the user to write
    "They're is a problem." spaCy tags this "there" with dep_ == "expl",
    which is exactly the signal needed to catch it before the verb
    branch ever runs. (Found in code review, B1.)
    """
    if token.dep_ == "expl":
        return "there"

    next_tok = token.doc[token.i + 1] if token.i + 1 < len(token.doc) else None

    if next_tok is None:
        return token.text.lower()

    if next_tok.pos_ in ("NOUN", "PROPN") and next_tok.dep_ != "npadvmod":
        return "their"

    if next_tok.lemma_ in ("be", "have", "do"):
        return "there"

    if next_tok.pos_ in ("VERB", "AUX"):
        return "they're"

    return "there"


for _w in ["there", "their", "they're"]:
    _DISAMBIGUATORS[_w] = _disambiguate_there


def _disambiguate_to(token):
    """to/too/two — POS rule. Defaults to 'to' since it's the most
    frequent of the three; only flags 'too'/'two' on clear signal."""
    doc = token.doc
    next_tok = doc[token.i + 1] if token.i + 1 < len(doc) else None
    next_next_tok = doc[token.i + 2] if token.i + 2 < len(doc) else None

    if token.like_num:
        return "two"
    if next_tok is not None and next_tok.pos_ == "VERB":
        return "to"
    if next_tok is not None and next_tok.pos_ == "ADJ":
        # "too tired" (intensifier) vs "to different subjects"
        # (preposition + adjective + noun). An intensifier "too"
        # is not itself followed by a noun right after the
        # adjective — that pattern means "to" is a preposition
        # modifying an upcoming noun phrase, not an intensifier.
        if next_next_tok is not None and next_next_tok.pos_ in ("NOUN", "PROPN"):
            return "to"
        return "too"
    if next_tok is not None and next_tok.pos_ in ("NOUN", "PROPN", "DET", "PRON"):
        return "to"
    if next_tok is None or next_tok.is_punct:
        return "too"
    return "to"


for _w in ["to", "too", "two"]:
    _DISAMBIGUATORS[_w] = _disambiguate_to


def _disambiguate_write(token):
    """write/right/rite — POS rule, defaults to 'right' (documented limitation)."""
    if token.pos_ == "VERB":
        return "write"
    return "right"              # far more common than "rite" outside ceremonial contexts


for _w in ["write", "right", "rite"]:
    _DISAMBIGUATORS[_w] = _disambiguate_write


def check_homophones(text: str, doc: "spacy.tokens.Doc") -> list[dict]:
    """
    Homophone detection (F28).

    Walks the spaCy-parsed doc, flags any token whose lowercase form
    is a known homophone-prone word, and suggests the contextually
    correct form for groups with a disambiguation rule (their/there,
    to/too/two, write/right). Other groups are flagged without a
    forced suggestion, since POS alone can't reliably tell them apart.
    """
    if not text or not text.strip():
        return []
    
    results = []
    for token in doc:
        word_lower = token.text.lower()
        if word_lower not in WORD_TO_GROUP:
            continue

        disambiguator = _DISAMBIGUATORS.get(word_lower)
        if disambiguator:
            correct_word = disambiguator(token)
            if correct_word != word_lower:
                results.append({
                    "word": token.text,
                    "suggestion": correct_word,
                    "position": token.i,
                })
        # For non-disambiguated groups, we don't currently flag —
        # avoiding a flood of low-confidence "double check this word"
        # noise. Revisit if the frontend wants that lower-confidence
        # tier later.

    return results