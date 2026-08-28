"""
backend/routers/sessions.py — Owner: M3
Session logging endpoints (F37 reading, F38 writing).

POST /sessions/reading — logs a completed reading session, and
  upserts WordRepeatLog rows for HARD-labeled words in that session
  (Task 4.7). Min-30-second rule: sessions shorter than 30s are
  ignored entirely (session AND word-repeat logging both skipped).

POST /sessions/writing — logs a completed writing session into the
  EXISTING WritingSession table (not a new one).

DECISION (Task 4.7): only words labeled "Hard" are logged into
word_repeat_log, not every word in the session. Reasoning: this table
feeds Task 6.1 (Word Bank auto-population) and Task 5.4
(/analytics/difficult-words) — both are explicitly about difficult
vocabulary. Logging every word (including "a", "the", "is") would let
trivial high-frequency words dominate repeat_count and defeat the
purpose of both downstream features. Revisit only if the team
explicitly wants Medium included too.
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.routers.auth import get_current_user
from backend.models_temp import User, get_db, ReadingSession, WritingSession, WordRepeatLog, WordBank

router = APIRouter(prefix="/sessions", tags=["sessions"])


# ── Reading session (F37) ────────────────────────────────────────────
class ReadingSessionCreate(BaseModel):
    wpm: Optional[float] = None
    total_words: int
    hard_word_count: int
    repeat_count: int = 0
    duration_seconds: int
    source_type: str  # 'image' | 'pdf' | 'paste'
    simplified: bool = False
    complexity_score: Optional[float] = None
    # Input-only field, not stored on ReadingSession itself — drives
    # the WordRepeatLog upsert below. Each item: {"word": str, "label": str}
    words: List[dict] = []


def _upsert_word_repeat_log(db: Session, user_id: str, words: List[dict]):
    """For each HARD-labeled word in this session, find-or-create its
    WordRepeatLog row and increment repeat_count. Non-Hard words are
    skipped entirely — see module docstring for reasoning."""
    for item in words:
        word = item.get("word", "").strip().lower()
        label = item.get("label", "")
        if not word or label != "Hard":
            continue

        existing = (
            db.query(WordRepeatLog)
            .filter(WordRepeatLog.user_id == user_id, WordRepeatLog.word == word)
            .first()
        )
        if existing:
            existing.repeat_count += 1
            existing.difficulty_label = label
            existing.last_seen = datetime.datetime.utcnow()
            new_count = existing.repeat_count
        else:
            db.add(WordRepeatLog(
                user_id=user_id,
                word=word,
                repeat_count=1,
                difficulty_label=label,
                last_seen=datetime.datetime.utcnow(),
            ))
            new_count = 1

        _maybe_add_to_word_bank(db, user_id, word, label, new_count)

def _maybe_add_to_word_bank(db: Session, user_id: str, word: str, label: str, repeat_count: int):
    """F49: once a word's repeat_count crosses 3, add it to word_bank
    with default SM-2 state, if it isn't already there. Find-or-skip,
    not a blind insert — word_bank has a unique (user_id, word)
    constraint."""
    if repeat_count < 3:
        return

    already_in_bank = (
        db.query(WordBank)
        .filter(WordBank.user_id == user_id, WordBank.word == word)
        .first()
    )
    if already_in_bank:
        return

    db.add(WordBank(
        user_id=user_id,
        word=word,
        difficulty_label=label,
        sm2_ef=2.5,
        sm2_interval=1,
        sm2_repetitions=0,
        next_review=datetime.date.today(),
        total_drills=0,
    ))



@router.post("/reading")
async def log_reading_session(
    body: ReadingSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log a completed reading session. Sessions under 30 seconds are
    silently ignored — too short to be meaningful data, not an error."""
    if body.duration_seconds < 30:
        return {"logged": False, "reason": "session too short (<30s)"}

    session = ReadingSession(
        user_id=current_user.id,
        wpm=body.wpm,
        total_words=body.total_words,
        hard_word_count=body.hard_word_count,
        repeat_count=body.repeat_count,
        duration_seconds=body.duration_seconds,
        source_type=body.source_type,
        simplified=body.simplified,
        complexity_score=body.complexity_score,
    )
    db.add(session)

    _upsert_word_repeat_log(db, current_user.id, body.words)

    db.commit()
    db.refresh(session)

    return {"logged": True, "session_id": session.id}


# ── Writing session (F38) ────────────────────────────────────────────
class WritingSessionCreate(BaseModel):
    word_count: int
    spell_error_count: int = 0
    grammar_error_count: int = 0
    homophone_flag_count: int = 0


@router.post("/writing")
async def log_writing_session(
    body: WritingSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log a completed writing session into the existing WritingSession
    table (F48's template_used column is populated separately by M2's
    endpoint — this endpoint only sets the count fields)."""
    session = WritingSession(
        user_id=current_user.id,
        word_count=body.word_count,
        spell_error_count=body.spell_error_count,
        grammar_error_count=body.grammar_error_count,
        homophone_flag_count=body.homophone_flag_count,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {"logged": True, "session_id": session.id}