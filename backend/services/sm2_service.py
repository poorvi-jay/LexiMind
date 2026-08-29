"""
backend/services/sm2_service.py — Owner: M3
SM-2 spaced-repetition algorithm (F50).

Pure function, no database access — takes the current SM-2 state of a
word_bank entry plus a quality score (0-5) and returns the updated
state. This is the EXACT algorithm specified in the PRD, not a generic
internet SM-2 variant — constants and branching differ between
implementations, so this must match precisely.
"""

from __future__ import annotations

import datetime


def update_sm2(word_bank_entry, quality: int) -> dict:
    """Given a word_bank entry's current SM-2 state and a quality score
    (0-5, how well the user recalled the word), return the updated
    state: new easiness factor, interval, repetitions, next review
    date, and whether the word counts as mastered."""
    ef = word_bank_entry.sm2_ef
    reps = word_bank_entry.sm2_repetitions
    interval = word_bank_entry.sm2_interval

    if quality >= 3:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = round(interval * ef)
        reps += 1
    else:
        reps = 0
        interval = 1

    ef = max(1.3, ef + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))

    next_review = datetime.date.today() + datetime.timedelta(days=interval)
    mastered = (ef >= 2.5 and interval >= 21)

    return {
        'sm2_ef': round(ef, 2),
        'sm2_interval': interval,
        'sm2_repetitions': reps,
        'next_review': next_review,
        'mastered': mastered,
    }