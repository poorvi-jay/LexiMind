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

from backend.services.nlp_service import (
    check_grammar,
    check_phonetic,
    check_homophones,
)

router = APIRouter(prefix="/nlp", tags=["NLP"])


class CheckRequest(BaseModel):
    text: str


class CheckResponse(BaseModel):
    spelling: list[dict]
    grammar: list[dict]
    homophones: list[dict]


@router.post("/check", response_model=CheckResponse)
async def check(req: CheckRequest):
    """
    Run grammar, phonetic spelling, and homophone checks on the
    given text. Response shape is fixed per the PRD's endpoint
    contract: { spelling[], grammar[], homophones[] }.

    Only 'grammar' is populated for now. 'spelling' and
    'homophones' will be filled in by Tasks 3 and 4 without
    changing this response shape, so frontend integration can
    start against this contract immediately if needed.
    """
    return {
        "spelling": check_phonetic(req.text),
        "grammar": check_grammar(req.text),
        "homophones": check_homophones(req.text),
    }