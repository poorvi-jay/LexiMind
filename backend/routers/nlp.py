"""
NLP Router — Owner: M2
Exposes POST /nlp/check (F26-F28) and POST /nlp/predict (F29).

STATUS: Skeleton only — no endpoints yet.
IMPORTANT: These endpoints must NOT require auth yet. Per Build Guide
Section 9: "Build /nlp/check and /nlp/predict without auth first —
retrofit Depends(get_current_user) once Auth exists (Day 8)."
"""
from fastapi import APIRouter

router = APIRouter(prefix="/nlp", tags=["NLP"])

# Endpoints added starting Task 2.