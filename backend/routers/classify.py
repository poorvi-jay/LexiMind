"""
backend/routers/classify.py — Owner: M3
POST /classify — real ML word difficulty classifier (F33/F34).
Replaces M1's wordfreq-threshold placeholder. Delegates all
inference to classifier_service.py (Phase 2's trained RandomForest,
loaded once at import — see that file for model details).

Auth retrofitted to match every other router's convention
(Depends(get_current_user), same pattern as nlp.py's Day 8 retrofit).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List

from backend.routers.auth import get_current_user
from backend.models_temp import User
from backend.services.classifier_service import classify_words

router = APIRouter(prefix="/classify", tags=["classify"])


# ── request / response schemas ──────────────────────────────────────
class ClassifyRequest(BaseModel):
    # min_length removed (was min_length=1) — empty list must return
    # {"results": []}, not a 422, per Phase 1 audit + Build Guide 4.2.
    words: List[str] = Field(default_factory=list, max_length=5000)


class WordClassification(BaseModel):
    word: str
    label: str          # "Easy" | "Medium" | "Hard"
    confidence: float   # 0.0 – 1.0


class ClassifyResponse(BaseModel):
    results: List[WordClassification]


# ── endpoint ────────────────────────────────────────────────────────
@router.post("", response_model=ClassifyResponse)
async def classify(
    body: ClassifyRequest,
    current_user: User = Depends(get_current_user),
):
    """Classify a list of words as Easy / Medium / Hard using the
    trained model. Contract is frozen — {results: [{word, label,
    confidence}]} — do not change, per M1→M2 and M2→M3 handoffs."""
    try:
        results = classify_words(body.words)
        return ClassifyResponse(results=results)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))