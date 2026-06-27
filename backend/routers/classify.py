"""
backend/routers/classify.py
POST /classify — rule-based word difficulty classifier.
Uses wordfreq frequency bands until M3's ML model is ready.

Thresholds:
  frequency > 1e-4  → Easy
  1e-5 ≤ freq ≤ 1e-4 → Medium
  frequency < 1e-5   → Hard
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from wordfreq import word_frequency
from typing import List

router = APIRouter(prefix="/classify", tags=["classify"])


# ── request / response schemas ──────────────────────────────────────
class ClassifyRequest(BaseModel):
    words: List[str] = Field(..., min_length=1, max_length=5000)


class WordClassification(BaseModel):
    word: str
    label: str          # "Easy" | "Medium" | "Hard"
    confidence: float   # 0.0 – 1.0


class ClassifyResponse(BaseModel):
    results: List[WordClassification]


# ── helper ──────────────────────────────────────────────────────────
def _classify_word(word: str) -> WordClassification:
    """Classify a single word using wordfreq frequency bands."""
    clean = word.strip().lower()
    if not clean:
        return WordClassification(word=word, label="Easy", confidence=0.5)

    freq = word_frequency(clean, "en")

    if freq > 1e-4:
        label, confidence = "Easy", min(1.0, freq * 1_000)
    elif freq >= 1e-6:
        label, confidence = "Medium", 0.6
    else:
        confidence = 0.85 if freq == 0 else 0.7
        label = "Hard"

    return WordClassification(word=word, label=label, confidence=round(confidence, 3))


# ── endpoint ────────────────────────────────────────────────────────
@router.post("", response_model=ClassifyResponse)
async def classify_words(body: ClassifyRequest):
    """Classify a list of words as Easy / Medium / Hard."""
    try:
        results = [_classify_word(w) for w in body.words]
        return ClassifyResponse(results=results)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))