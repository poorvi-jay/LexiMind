"""
backend/routers/reading.py
Endpoints: /reading/simplify, /reading/complexity, /reading/define
Task 2 — syllable count now uses NLTK CMU Pronouncing Dictionary,
         falling back to vowel heuristic only when word is absent.
Also enriches /reading/define response with all meanings + syllable_count.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.services import simplification_service
from backend.routers.auth import get_current_user
import httpx
import re

# ── CMU dict for accurate syllable counts (Task 2) ─────────────────
import nltk
from nltk.corpus import cmudict as _cmudict_module

try:
    _cmu = _cmudict_module.dict()
except LookupError:
    nltk.download("cmudict", quiet=True)
    _cmu = _cmudict_module.dict()

# ── WordNet: offline definitions when dictionaryapi.dev is down ────
from nltk.corpus import wordnet as _wn

try:
    _wn.ensure_loaded()
except LookupError:
    nltk.download("wordnet", quiet=True)
    nltk.download("omw-1.4", quiet=True)
    _wn.ensure_loaded()

_WN_POS = {"n": "noun", "v": "verb", "a": "adjective", "s": "adjective", "r": "adverb"}


router = APIRouter()


class SimplifyRequest(BaseModel):
    text: str


class ComplexityRequest(BaseModel):
    text: str


class DefineRequest(BaseModel):
    word: str


# ── syllable helpers (Task 2) ──────────────────────────────────────
def _syllables_cmu(word: str):
    """Return syllable count from CMU dict, or None if word not found."""
    pronunciations = _cmu.get(word.lower().strip())
    if not pronunciations:
        return None
    # Each phoneme that ends with a digit represents a vowel nucleus
    return sum(1 for phoneme in pronunciations[0] if phoneme[-1].isdigit())


def _syllables_vowel(word: str) -> int:
    """Fallback heuristic: count vowel groups."""
    word = word.lower().strip()
    if not word:
        return 0
    count = len(re.findall(r'[aeiouy]+', word))
    # silent-e adjustment
    if word.endswith('e') and count > 1:
        count -= 1
    return max(1, count)


def count_syllables(word: str) -> int:
    """Accurate syllable count: CMU dict first, vowel fallback second."""
    cmu_count = _syllables_cmu(word)
    if cmu_count is not None:
        return cmu_count
    return _syllables_vowel(word)


def _wordnet_meanings(word: str, max_per_pos: int = 3):
    """Meanings in the dictionaryapi.dev shape, or [] if WordNet lacks the word."""
    grouped = {}
    for synset in _wn.synsets(word):
        pos = _WN_POS.get(synset.pos(), synset.pos())
        defs = grouped.setdefault(pos, [])
        if len(defs) >= max_per_pos:
            continue
        entry = {"definition": synset.definition()}
        if synset.examples():
            entry["example"] = synset.examples()[0]
        defs.append(entry)
    return [{"partOfSpeech": pos, "definitions": defs} for pos, defs in grouped.items()]


def _build_definition(word, phonetic, meanings, syllable_count, source):
    definition = next((d["definition"] for m in meanings for d in m["definitions"]), "")
    example = next(
        (d["example"] for m in meanings for d in m["definitions"] if d.get("example")), ""
    )
    return {
        "word": word,
        "phonetic": phonetic,
        "definition": definition,
        "example": example,
        "syllable_count": syllable_count,
        "syllables": syllable_count,       # kept for backward compat
        "meanings": meanings,              # full meanings for AC-34
        "source": source,
    }


# ── endpoints ──────────────────────────────────────────────────────

@router.post("/reading/simplify")
async def simplify(
    req: SimplifyRequest,
    current_user: dict = Depends(get_current_user)
):
    if not req.text.strip():
        raise HTTPException(400, "No text provided.")
    return await simplification_service.simplify_text(req.text)


@router.post("/reading/complexity")
async def complexity(
    req: ComplexityRequest,
    current_user: dict = Depends(get_current_user)
):
    if not req.text.strip():
        raise HTTPException(400, "No text provided.")
    return await simplification_service.get_complexity(req.text)


@router.post("/reading/define")
async def define_word(
    req: DefineRequest,
    current_user: dict = Depends(get_current_user)
):
    word = req.word.strip().lower()
    if not word:
        raise HTTPException(400, "No word provided.")

    # ── Task 2: accurate syllable count ────────────────────────────
    syllable_count = count_syllables(word)

    # ── online dictionary (phonetics + richer data) ────────────────
    # dictionaryapi.dev is free and often slow or down, so keep the
    # timeout short and fall back to offline WordNet on any failure.
    entry = None
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(
                f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
            )
        if response.status_code == 200:
            entry = response.json()[0]
    except (httpx.HTTPError, ValueError, IndexError, KeyError, TypeError):
        entry = None

    if entry is None:
        # Offline fallback. morphy maps inflections ("studies" → "study").
        meanings = _wordnet_meanings(word) or _wordnet_meanings(_wn.morphy(word) or word)
        if not meanings:
            raise HTTPException(404, "Definition not found. Try a different form of the word.")
        return _build_definition(word, "", meanings, syllable_count, "wordnet")

    # Extract phonetic
    phonetic = entry.get("phonetic", "")
    if not phonetic:
        phonetic = next((ph["text"] for ph in entry.get("phonetics", []) if ph.get("text")), "")

    meanings = []
    for m in entry.get("meanings", []):
        defs_out = []
        for d in m.get("definitions", []):
            def_entry = {"definition": d.get("definition", "")}
            if d.get("example"):
                def_entry["example"] = d["example"]
            defs_out.append(def_entry)
        meanings.append({"partOfSpeech": m.get("partOfSpeech", ""), "definitions": defs_out})

    return _build_definition(word, phonetic, meanings, syllable_count, "dictionaryapi")