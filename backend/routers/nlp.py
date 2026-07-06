"""
NLP Router — Owner: M2
Exposes POST /nlp/check (F26-F28) and POST /nlp/predict (F29).

STATUS:
- /nlp/check: grammar (F27), phonetic spelling (F26), and
  homophone detection (F28) all implemented.
- /nlp/predict: word/phrase prediction (F29) implemented via
  local DistilGPT-2.
- Both endpoints now require authentication (Day 8 retrofit,
  Task 9) via Depends(get_current_user). Built unauthenticated
  first per Build Guide Section 9, retrofitted once Auth existed.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from backend.services.prediction_service import predict_words, predict_phrase
from backend.routers.auth import get_current_user
from backend.models_temp import User
from backend.services.nlp_service import (
    check_grammar,
    check_phonetic,
    check_homophones,
    nlp as spacy_nlp,
)

router = APIRouter(prefix="/nlp", tags=["NLP"])


class CheckRequest(BaseModel):
    text: str


class CheckResponse(BaseModel):
    spelling: list[dict]
    grammar: list[dict]
    homophones: list[dict]

class PredictRequest(BaseModel):
    prefix: str


class PredictResponse(BaseModel):
    suggestions: list[str]
    phrase_suggestion: str


@router.post("/check", response_model=CheckResponse)
async def check(req: CheckRequest, current_user: User = Depends(get_current_user)):
    """
    Run grammar, phonetic spelling, and homophone checks on the
    given text. Response shape per PRD Section 3 contract:
    { spelling[], grammar[], homophones[] }

    Now requires authentication (Day 8 retrofit) — a valid Bearer
    token must be provided.
    """
    doc = spacy_nlp(req.text)
    return {
        "spelling": check_phonetic(req.text),
        "grammar": check_grammar(req.text),
        "homophones": check_homophones(req.text, doc),
    }


@router.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest, current_user: User = Depends(get_current_user)):
    """
    Generate word/phrase completions for the given text prefix.
    Response shape per PRD contract: { suggestions[3], phrase_suggestion }

    Now requires authentication (Day 8 retrofit) — a valid Bearer
    token must be provided.
    """
    return {
        "suggestions": predict_words(req.prefix),
        "phrase_suggestion": predict_phrase(req.prefix),
    }

