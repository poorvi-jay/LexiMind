"""
NLP Router — Owner: M2
Exposes POST /nlp/check (F26-F28) and POST /nlp/predict (F29).

STATUS:
- /nlp/check: grammar (F27) implemented. spelling (F26) and
  homophones (F28) return empty lists until Tasks 3-4.
- /nlp/predict: not yet implemented (Task 5+).

IMPORTANT: No auth dependency yet. Per Build Guide Section 9,
add Depends(get_current_user) once Auth (Phase 3) is built —
don't add it now, it would block testing before Auth exists.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from backend.services.prediction_service import predict_words, predict_phrase
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


@router.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    """
    Generate word/phrase completions for the given text prefix.
    Response shape per PRD contract: { suggestions[3], phrase_suggestion }
    phrase_suggestion is "" (never an error) when unusable — AC-22.
    """
    return {
        "suggestions": predict_words(req.prefix),
        "phrase_suggestion": predict_phrase(req.prefix),
    }

@router.post("/check", response_model=CheckResponse)
async def check(req: CheckRequest):
    doc = spacy_nlp(req.text)
    return {
        "spelling": check_phonetic(req.text),
        "grammar": check_grammar(req.text),
        "homophones": check_homophones(req.text, doc),
    }