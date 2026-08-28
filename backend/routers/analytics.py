"""
backend/routers/analytics.py — Owner: M3
Analytics endpoints (F39-F41) — read-only aggregates over session
data logged by sessions.py (Phase 4). Every query scoped to
current_user.id (Task 5.5) — no exceptions.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.routers.auth import get_current_user
from backend.models_temp import User, get_db, ReadingSession, WritingSession, WordRepeatLog
router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
async def get_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Total sessions, total words read, avg WPM, best WPM — all time,
    scoped to the current user. Returns zeroed values for a brand-new
    user with no sessions yet (Task 5.6), not a 404/500."""
    result = (
        db.query(
            func.count(ReadingSession.id).label("total_sessions"),
            func.sum(ReadingSession.total_words).label("total_words"),
            func.avg(ReadingSession.wpm).label("avg_wpm"),
            func.max(ReadingSession.wpm).label("best_wpm"),
        )
        .filter(ReadingSession.user_id == current_user.id)
        .one()
    )
    return {
        "total_sessions": result.total_sessions or 0,
        "total_words": result.total_words or 0,
        "avg_wpm": round(result.avg_wpm, 1) if result.avg_wpm else 0,
        "best_wpm": result.best_wpm or 0,
    }


@router.get("/reading")
async def get_reading_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Last 20 reading sessions with metrics, ordered by date descending,
    scoped to the current user. Returns an empty list for a brand-new
    user with no sessions yet (Task 5.6), not a 404/500."""
    sessions = (
        db.query(ReadingSession)
        .filter(ReadingSession.user_id == current_user.id)
        .order_by(ReadingSession.date.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": s.id,
            "date": s.date.isoformat() if s.date else None,
            "wpm": s.wpm,
            "total_words": s.total_words,
            "hard_word_count": s.hard_word_count,
            "repeat_count": s.repeat_count,
            "duration_seconds": s.duration_seconds,
            "source_type": s.source_type,
            "simplified": s.simplified,
            "complexity_score": s.complexity_score,
        }
        for s in sessions
    ]

@router.get("/writing")
async def get_writing_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Last 20 writing sessions with error counts and error rate,
    ordered by date descending, scoped to the current user. Returns
    an empty list for a brand-new user (Task 5.6), not a 404/500.

    Pre-F38 historical rows may have word_count=0 or null error
    counts (M2->M3 handoff, Section 10/17) — error_rate is null in
    that case rather than raising a ZeroDivisionError."""
    sessions = (
        db.query(WritingSession)
        .filter(WritingSession.user_id == current_user.id)
        .order_by(WritingSession.date.desc())
        .limit(20)
        .all()
    )

    def error_rate(s: WritingSession):
        if not s.word_count:
            return None
        total_errors = (
            (s.spell_error_count or 0)
            + (s.grammar_error_count or 0)
            + (s.homophone_flag_count or 0)
        )
        return round((total_errors / s.word_count) * 100, 1)

    return [
        {
            "id": s.id,
            "date": s.date.isoformat() if s.date else None,
            "word_count": s.word_count or 0,
            "spell_error_count": s.spell_error_count or 0,
            "grammar_error_count": s.grammar_error_count or 0,
            "homophone_flag_count": s.homophone_flag_count or 0,
            "template_used": s.template_used,
            "error_rate": error_rate(s),
        }
        for s in sessions
    ]



@router.get("/difficult-words")
async def get_difficult_words(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Top 10 words by repeat_count, scoped to the current user.
    word_repeat_log only ever logs Hard-labeled words (Phase 4 design
    decision), so no extra difficulty filtering is needed here.
    Returns an empty list for a brand-new user (Task 5.6)."""
    words = (
        db.query(WordRepeatLog)
        .filter(WordRepeatLog.user_id == current_user.id)
        .order_by(WordRepeatLog.repeat_count.desc())
        .limit(10)
        .all()
    )
    return [
        {
            "word": w.word,
            "repeat_count": w.repeat_count,
            "difficulty_label": w.difficulty_label,
            "last_seen": w.last_seen.isoformat() if w.last_seen else None,
        }
        for w in words
    ]