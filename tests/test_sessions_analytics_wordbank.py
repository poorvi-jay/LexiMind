"""
tests/test_sessions_analytics_wordbank.py — Owner: M4
Phase 2 (held portion) — Sessions (F37/F38), Analytics (F39-F41),
Word Bank (F49-F51).

Marked m3_inflight: these are the tables M3's Postgres migration is
re-keying, and AnalyticsPage is being changed right now. They pass on
today's schema; CI runs them non-blocking until Phase 1 lands, then
the marker comes off and they become blocking. If a response shape
changes as part of M3's analytics work, update the assertions here —
don't patch the router (M4 guide section 8).
"""
import datetime

import pytest

from tests.conftest import models

pytestmark = pytest.mark.m3_inflight


def reading_payload(**overrides):
    body = {
        "wpm": 120.0,
        "total_words": 240,
        "hard_word_count": 6,
        "repeat_count": 2,
        "duration_seconds": 120,
        "source_type": "paste",
        "simplified": False,
        "complexity_score": 7.5,
        "words": [],
    }
    body.update(overrides)
    return body


# ── /sessions ───────────────────────────────────────────────────────
def test_reading_session_logged(client, auth_headers):
    res = client.post("/sessions/reading", json=reading_payload(), headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["logged"] is True
    assert body["session_id"]


def test_reading_session_under_30s_ignored(client, auth_headers):
    res = client.post(
        "/sessions/reading", json=reading_payload(duration_seconds=29), headers=auth_headers
    )
    assert res.status_code == 200
    assert res.json()["logged"] is False
    assert client.get("/analytics/summary", headers=auth_headers).json()["total_sessions"] == 0


def test_reading_session_logs_only_hard_words(client, auth_headers):
    words = [
        {"word": "Photosynthesis", "label": "Hard"},
        {"word": "the", "label": "Easy"},
        {"word": "process", "label": "Medium"},
    ]
    client.post("/sessions/reading", json=reading_payload(words=words), headers=auth_headers)
    difficult = client.get("/analytics/difficult-words", headers=auth_headers).json()
    assert [w["word"] for w in difficult] == ["photosynthesis"]  # lowercased
    assert difficult[0]["repeat_count"] == 1


def test_reading_session_validation(client, auth_headers):
    res = client.post("/sessions/reading", json={"wpm": 100}, headers=auth_headers)
    assert res.status_code == 422


def test_writing_session_logged(client, auth_headers):
    res = client.post(
        "/sessions/writing",
        json={"word_count": 200, "spell_error_count": 4, "grammar_error_count": 2,
              "homophone_flag_count": 2},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["logged"] is True


# ── /analytics ──────────────────────────────────────────────────────
def test_analytics_new_user_zeroed_not_error(client, auth_headers):
    """Task 5.6: brand-new user gets zeros/empty lists, never 404/500."""
    assert client.get("/analytics/summary", headers=auth_headers).json() == {
        "total_sessions": 0, "total_words": 0, "avg_wpm": 0, "best_wpm": 0,
    }
    for path in ("/analytics/reading", "/analytics/writing", "/analytics/difficult-words"):
        res = client.get(path, headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []


def test_analytics_summary_aggregates(client, auth_headers):
    client.post("/sessions/reading", json=reading_payload(wpm=100.0, total_words=200),
                headers=auth_headers)
    client.post("/sessions/reading", json=reading_payload(wpm=150.0, total_words=300),
                headers=auth_headers)
    summary = client.get("/analytics/summary", headers=auth_headers).json()
    assert summary == {"total_sessions": 2, "total_words": 500, "avg_wpm": 125.0,
                       "best_wpm": 150.0}


def test_analytics_reading_history_shape(client, auth_headers):
    client.post("/sessions/reading", json=reading_payload(source_type="pdf", simplified=True),
                headers=auth_headers)
    history = client.get("/analytics/reading", headers=auth_headers).json()
    assert len(history) == 1
    row = history[0]
    assert set(row) >= {"id", "date", "wpm", "total_words", "hard_word_count",
                        "repeat_count", "duration_seconds", "source_type", "simplified",
                        "complexity_score"}
    assert row["source_type"] == "pdf"
    assert row["simplified"] is True


def test_analytics_reading_history_capped_at_20(client, auth_headers):
    for _ in range(22):
        client.post("/sessions/reading", json=reading_payload(), headers=auth_headers)
    assert len(client.get("/analytics/reading", headers=auth_headers).json()) == 20


def test_analytics_writing_error_rate(client, auth_headers):
    client.post(
        "/sessions/writing",
        json={"word_count": 200, "spell_error_count": 4, "grammar_error_count": 2,
              "homophone_flag_count": 2},
        headers=auth_headers,
    )
    # F48 template-only rows have word_count=0 -> error_rate None, not a crash
    client.post("/writing/template-used", json={"template": "essay"}, headers=auth_headers)
    rows = client.get("/analytics/writing", headers=auth_headers).json()
    assert len(rows) == 2
    rates = sorted((r["error_rate"] for r in rows), key=lambda v: (v is not None, v))
    assert rates == [None, 4.0]  # (4+2+2)/200*100


def test_difficult_words_top10_by_repeat(client, auth_headers):
    for i in range(12):
        words = [{"word": f"word{j}", "label": "Hard"} for j in range(i + 1)]
        client.post("/sessions/reading", json=reading_payload(words=words), headers=auth_headers)
    top = client.get("/analytics/difficult-words", headers=auth_headers).json()
    assert len(top) == 10
    assert top[0] == {**top[0], "word": "word0", "repeat_count": 12}
    counts = [w["repeat_count"] for w in top]
    assert counts == sorted(counts, reverse=True)


# ── /wordbank ───────────────────────────────────────────────────────
def _log_hard_word(client, headers, word, times):
    for _ in range(times):
        client.post(
            "/sessions/reading",
            json=reading_payload(words=[{"word": word, "label": "Hard"}]),
            headers=headers,
        )


def test_wordbank_auto_add_after_three_repeats(client, auth_headers):
    _log_hard_word(client, auth_headers, "ephemeral", 2)
    assert client.get("/wordbank", headers=auth_headers).json() == []

    _log_hard_word(client, auth_headers, "ephemeral", 1)
    bank = client.get("/wordbank", headers=auth_headers).json()
    assert [w["word"] for w in bank] == ["ephemeral"]
    entry = bank[0]
    assert entry["sm2_ef"] == 2.5
    assert entry["sm2_interval"] == 1
    assert entry["sm2_repetitions"] == 0
    assert entry["mastered"] is False

    # 4th repeat must not duplicate (unique user_id+word)
    _log_hard_word(client, auth_headers, "ephemeral", 1)
    assert len(client.get("/wordbank", headers=auth_headers).json()) == 1


def test_wordbank_stats(client, auth_headers):
    assert client.get("/wordbank/stats", headers=auth_headers).json() == {
        "due_count": 0, "total_words": 0,
    }
    _log_hard_word(client, auth_headers, "ubiquitous", 3)
    assert client.get("/wordbank/stats", headers=auth_headers).json() == {
        "due_count": 1, "total_words": 1,
    }


def test_drill_returns_due_words_only(client, auth_headers, db, register_user):
    _log_hard_word(client, auth_headers, "ubiquitous", 3)
    _log_hard_word(client, auth_headers, "esoteric", 3)
    # Push one word's review into the future
    row = db.query(models.WordBank).filter(models.WordBank.word == "esoteric").one()
    row.next_review = datetime.date.today() + datetime.timedelta(days=5)
    db.commit()

    drill = client.get("/wordbank/drill", headers=auth_headers).json()
    assert [w["word"] for w in drill] == ["ubiquitous"]
    assert len(client.get("/wordbank", headers=auth_headers).json()) == 2  # AC-39: all words


def test_drill_capped_at_20(client, auth_headers, db):
    me = client.get("/auth/me", headers=auth_headers).json()
    for i in range(25):
        db.add(models.WordBank(user_id=me["id"], word=f"w{i}", difficulty_label="Hard",
                               next_review=datetime.date.today()))
    db.commit()
    assert len(client.get("/wordbank/drill", headers=auth_headers).json()) == 20


@pytest.mark.parametrize("quality,expected", [
    # (quality) -> (ef, interval, repetitions) from a fresh word (2.5, 1, 0)
    (1, (1.96, 1, 0)),
    (3, (2.36, 1, 1)),
    (4, (2.5, 1, 1)),
    (5, (2.6, 1, 1)),
])
def test_drill_result_sm2_update(client, auth_headers, quality, expected):
    """The four quality values the drill UI sends (1, 3, 4, 5)."""
    _log_hard_word(client, auth_headers, "ubiquitous", 3)
    res = client.post("/wordbank/drill/result", json={"word": "ubiquitous", "quality": quality},
                      headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert (body["sm2_ef"], body["sm2_interval"], body["sm2_repetitions"]) == expected
    assert body["total_drills"] == 1
    expected_next = datetime.date.today() + datetime.timedelta(days=expected[1])
    assert body["next_review"] == expected_next.isoformat()


def test_drill_result_sequence_grows_interval(client, auth_headers):
    _log_hard_word(client, auth_headers, "ubiquitous", 3)
    intervals = []
    for _ in range(3):
        body = client.post("/wordbank/drill/result",
                           json={"word": "ubiquitous", "quality": 5},
                           headers=auth_headers).json()
        intervals.append(body["sm2_interval"])
    assert intervals == [1, 6, 16]  # round(6 * 2.7)


def test_drill_result_validation(client, auth_headers):
    _log_hard_word(client, auth_headers, "ubiquitous", 3)
    res = client.post("/wordbank/drill/result", json={"word": "ubiquitous", "quality": 6},
                      headers=auth_headers)
    assert res.status_code == 422
    res = client.post("/wordbank/drill/result", json={"word": "not-in-bank", "quality": 4},
                      headers=auth_headers)
    assert res.status_code == 404


def test_wordbank_syllables(client, auth_headers):
    res = client.get("/wordbank/syllables", params={"word": " Elephant "}, headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["word"] == "elephant"
    assert "".join(body["syllables"]) == "elephant"
    assert len(body["syllables"]) >= 2
