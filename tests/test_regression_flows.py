"""
tests/test_regression_flows.py — Owner: M4
Phase 3 — the end-to-end flows M3 verified by hand (M4 guide section 6),
driven through the API in the same order the frontend calls them.

Reading + Writing flows are DB-independent and blocking in CI.
Analytics + Word Bank flows are marked m3_inflight (Phase 1).

Known gap, NOT a bug to "discover" (M4 guide 3d): the Reading page logs
a session from handleStop() only, so playback that ends naturally
without a Stop click is never logged. That's frontend behaviour; the
flow below logs on Stop, as the UI does today.
"""
import re

import pytest

from tests.conftest import FAKE_OCR_TEXT
from tests.test_reading_endpoints import PNG_1PX


def _tokens(text):
    return re.findall(r"[A-Za-z']+", text)


def test_reading_flow(client, auth_headers, monkeypatch):
    # 1. upload -> OCR
    ocr = client.post("/ocr/image", files={"file": ("p.png", PNG_1PX, "image/png")},
                      headers=auth_headers).json()
    words = _tokens(ocr["text"])
    assert ocr["text"] == FAKE_OCR_TEXT

    # 2. complexity badge
    cx = client.post("/reading/complexity", json={"text": ocr["text"]},
                     headers=auth_headers).json()
    assert cx["word_count"] == len(words)

    # 3. /classify -> Hard-word highlight (real model)
    results = client.post("/classify", json={"words": words},
                          headers=auth_headers).json()["results"]
    assert [r["word"] for r in results] == words
    hard = [r["word"] for r in results if r["label"] == "Hard"]
    assert "photosynthesis" in hard

    # 4. simplify (Groq faked)
    simple = client.post("/reading/simplify", json={"text": ocr["text"]},
                         headers=auth_headers).json()
    assert simple["simplified_text"]

    # 5. TTS playback: one timing per displayed word for highlight sync
    tts = client.post("/tts/generate", json={"text": ocr["text"]}, headers=auth_headers).json()
    assert [t["word"] for t in tts["word_timings"]] == ocr["text"].split()
    starts = [t["start_ms"] for t in tts["word_timings"]]
    assert starts == sorted(starts)

    # 6. Stop click -> session logged with the classifier's labels
    logged = client.post(
        "/sessions/reading",
        json={
            "wpm": 110.0, "total_words": len(words), "hard_word_count": len(hard),
            "repeat_count": 1, "duration_seconds": 45, "source_type": "image",
            "simplified": True, "complexity_score": cx["flesch_kincaid_grade"],
            "words": [{"word": r["word"], "label": r["label"]} for r in results],
        },
        headers=auth_headers,
    ).json()
    assert logged["logged"] is True


def test_writing_flow(client, auth_headers):
    text = "I went their yesterday becuase"
    # 1. type -> /nlp/check
    check = client.post("/nlp/check", json={"text": text}, headers=auth_headers).json()
    assert set(check) == {"spelling", "grammar", "homophones"}
    # 2. /nlp/predict -> 3 words + phrase pill
    pred = client.post("/nlp/predict", json={"prefix": text}, headers=auth_headers).json()
    assert len(pred["suggestions"]) == 3
    assert pred["phrase_suggestion"]
    # 3. autosave, then reload restores it
    client.patch("/writing/autosave", json={"content": text}, headers=auth_headers)
    assert client.get("/writing/autosave", headers=auth_headers).json()["content"] == text
    # 4. tab hidden (visibilitychange) -> session logged
    res = client.post(
        "/sessions/writing",
        json={"word_count": len(text.split()),
              "spell_error_count": len(check["spelling"]),
              "grammar_error_count": len(check["grammar"]),
              "homophone_flag_count": len(check["homophones"])},
        headers=auth_headers,
    )
    assert res.json()["logged"] is True
    # 5. Save As -> named doc, separate from the draft
    doc_id = client.post("/writing/documents",
                         json={"title": "Diary", "content": text, "template": None},
                         headers=auth_headers).json()["id"]
    assert [d["id"] for d in client.get("/writing/documents", headers=auth_headers).json()] \
        == [doc_id]


@pytest.mark.m3_inflight
def test_analytics_flow(client, two_users):
    alice, bob = two_users
    client.post(
        "/sessions/reading",
        json={"wpm": 140.0, "total_words": 280, "hard_word_count": 3, "duration_seconds": 120,
              "source_type": "pdf", "words": [{"word": "ubiquitous", "label": "Hard"}]},
        headers=alice["headers"],
    )
    client.post("/sessions/writing", json={"word_count": 100, "spell_error_count": 5},
                headers=alice["headers"])

    # Shows up in every /analytics/* query AnalyticsPage renders
    summary = client.get("/analytics/summary", headers=alice["headers"]).json()
    assert summary["total_sessions"] == 1 and summary["best_wpm"] == 140.0
    assert len(client.get("/analytics/reading", headers=alice["headers"]).json()) == 1
    assert client.get("/analytics/writing",
                      headers=alice["headers"]).json()[0]["error_rate"] == 5.0
    assert client.get("/analytics/difficult-words",
                      headers=alice["headers"]).json()[0]["word"] == "ubiquitous"

    # Cross-account isolation holds
    assert client.get("/analytics/summary", headers=bob["headers"]).json()["total_sessions"] == 0
    for path in ("/analytics/reading", "/analytics/writing", "/analytics/difficult-words"):
        assert client.get(path, headers=bob["headers"]).json() == []


@pytest.mark.m3_inflight
def test_wordbank_flow(client, auth_headers):
    session = {"total_words": 50, "hard_word_count": 1, "duration_seconds": 60,
               "source_type": "paste", "words": [{"word": "Ephemeral", "label": "Hard"}]}
    # repeat 3x -> auto-added
    for _ in range(3):
        client.post("/sessions/reading", json=session, headers=auth_headers)
    # -> due today: NavBar badge / HomePage card
    assert client.get("/wordbank/stats", headers=auth_headers).json()["due_count"] == 1
    drill = client.get("/wordbank/drill", headers=auth_headers).json()
    assert [w["word"] for w in drill] == ["ephemeral"]
    syl = client.get("/wordbank/syllables", params={"word": "ephemeral"},
                     headers=auth_headers).json()
    assert "".join(syl["syllables"]) == "ephemeral"
    # answer -> SM-2 pushes next_review out -> no longer due
    res = client.post("/wordbank/drill/result", json={"word": "ephemeral", "quality": 4},
                      headers=auth_headers).json()
    assert res["sm2_repetitions"] == 1 and res["next_review"] > drill[0]["next_review"]
    assert client.get("/wordbank/drill", headers=auth_headers).json() == []
    assert client.get("/wordbank/stats", headers=auth_headers).json() == {
        "due_count": 0, "total_words": 1,
    }
