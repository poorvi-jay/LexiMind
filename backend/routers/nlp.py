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
def check(req: CheckRequest, current_user: User = Depends(get_current_user)):
    """
    Run grammar, phonetic spelling, and homophone checks on the
    given text. Response shape per PRD Section 3 contract:
    { spelling[], grammar[], homophones[] }

    Now requires authentication (Day 8 retrofit) — a valid Bearer
    token must be provided.

    Plain `def`, not `async def` (B2 fix): the body does blocking
    CPU/subprocess work (spaCy parsing, a LanguageTool Java
    round-trip) with no awaits. As `async def` this blocked the
    entire event loop — every other request, for every user —
    for the duration of the call. FastAPI runs a plain `def`
    endpoint in a worker thread instead, keeping the event loop
    free.
    """
    doc = spacy_nlp(req.text)
    return {
        "spelling": check_phonetic(req.text),
        "grammar": check_grammar(req.text),
        "homophones": check_homophones(req.text, doc),
    }


@router.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest, current_user: User = Depends(get_current_user)):
    """
    Generate word/phrase completions for the given text prefix.
    Response shape per PRD contract: { suggestions[3], phrase_suggestion }

    Now requires authentication (Day 8 retrofit) — a valid Bearer
    token must be provided.

    Plain `def`, not `async def` (B2 fix): DistilGPT-2's
    model.generate() is blocking, synchronous CPU work with no
    awaits — same reasoning as check() above.
    """
    return {
        "suggestions": predict_words(req.prefix),
        "phrase_suggestion": predict_phrase(req.prefix),
    }