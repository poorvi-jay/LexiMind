"""
backend/routers/wordbank.py — Owner: M3
Word Bank drill endpoints (F50).

GET /wordbank/drill — words due for review today, scoped to the
  current user, capped at 20 even if more are due.
POST /wordbank/drill/result — records a drill answer and updates the
  word's SM-2 state via sm2_service.update_sm2().
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.routers.auth import get_current_user
from backend.models_temp import User, get_db, WordBank
from backend.services.sm2_service import update_sm2

router = APIRouter(prefix="/wordbank", tags=["wordbank"])


@router.get("/drill")
async def get_drill_words(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Words due for review today (next_review <= today), scoped to
    the current user, capped at 20 per session even if more are due."""
    words = (
        db.query(WordBank)
        .filter(
            WordBank.user_id == current_user.id,
            WordBank.next_review <= datetime.date.today(),
        )
        .order_by(WordBank.next_review.asc())
        .limit(20)
        .all()
    )
    return [
        {
            "word": w.word,
            "difficulty_label": w.difficulty_label,
            "sm2_ef": w.sm2_ef,
            "sm2_interval": w.sm2_interval,
            "sm2_repetitions": w.sm2_repetitions,
            "next_review": w.next_review.isoformat() if w.next_review else None,
            "total_drills": w.total_drills,
        }
        for w in words
    ]


class DrillResultBody(BaseModel):
    word: str
    quality: int  # 0-5


@router.post("/drill/result")
async def submit_drill_result(
    body: DrillResultBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a drill answer, run it through the SM-2 algorithm, and
    persist the updated state."""
    if not (0 <= body.quality <= 5):
        raise HTTPException(status_code=422, detail="quality must be between 0 and 5")

    entry = (
        db.query(WordBank)
        .filter(WordBank.user_id == current_user.id, WordBank.word == body.word)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="word not found in word bank")

    result = update_sm2(entry, body.quality)

    entry.sm2_ef = result["sm2_ef"]
    entry.sm2_interval = result["sm2_interval"]
    entry.sm2_repetitions = result["sm2_repetitions"]
    entry.next_review = result["next_review"]
    entry.total_drills += 1
    entry.last_quality = body.quality

    db.commit()
    db.refresh(entry)

    return {
        "word": entry.word,
        "sm2_ef": entry.sm2_ef,
        "sm2_interval": entry.sm2_interval,
        "sm2_repetitions": entry.sm2_repetitions,
        "next_review": entry.next_review.isoformat(),
        "total_drills": entry.total_drills,
        "mastered": result["mastered"],
    }

@router.get("/stats")
async def get_wordbank_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """F51: counts used to power the NavBar badge and HomePage
    drill-due reminder card."""
    due_count = (
        db.query(WordBank)
        .filter(
            WordBank.user_id == current_user.id,
            WordBank.next_review <= datetime.date.today(),
        )
        .count()
    )
    total_words = (
        db.query(WordBank)
        .filter(WordBank.user_id == current_user.id)
        .count()
    )
    return {
        "due_count": due_count,
        "total_words": total_words,
    }