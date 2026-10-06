"""
tests/test_reading_endpoints.py — Owner: M4
Phase 2 — OCR / TTS / Reading endpoints (M1: F05-F20, F42-F44).
DB-independent. EasyOCR, edge-tts and Groq are faked (see conftest);
the request validation and response contracts are what's under test.
"""
import httpx
import pytest

from backend.services.simplification_service import simplify_text as real_simplify_text
from tests.conftest import FAKE_OCR_TEXT, FAKE_SIMPLIFIED

PNG_1PX = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01"
    b"\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


# ── OCR ─────────────────────────────────────────────────────────────
def test_ocr_image_returns_text_and_word_count(client, auth_headers):
    res = client.post(
        "/ocr/image",
        files={"file": ("page.png", PNG_1PX, "image/png")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["text"] == FAKE_OCR_TEXT
    assert body["word_count"] == len(FAKE_OCR_TEXT.split())


def test_ocr_image_rejects_wrong_type(client, auth_headers):
    res = client.post(
        "/ocr/image",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers=auth_headers,
    )
    assert res.status_code == 422


def test_ocr_image_rejects_over_10mb(client, auth_headers):
    big = b"\x00" * (10_000_001)
    res = client.post(
        "/ocr/image",
        files={"file": ("big.jpg", big, "image/jpeg")},
        headers=auth_headers,
    )
    assert res.status_code == 413


def test_ocr_pdf_returns_pages(client, auth_headers):
    res = client.post(
        "/ocr/pdf",
        files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["pages"] == 2
    assert body["page_texts"] == ["Page one text.", "Page two text."]
    assert body["text"] == "Page one text.\nPage two text."
    assert body["word_count"] == 6


def test_ocr_pdf_rejects_non_pdf(client, auth_headers):
    res = client.post(
        "/ocr/pdf",
        files={"file": ("page.png", PNG_1PX, "image/png")},
        headers=auth_headers,
    )
    assert res.status_code == 422


# ── TTS ─────────────────────────────────────────────────────────────
def test_tts_generate_contract(client, auth_headers):
    res = client.post(
        "/tts/generate",
        json={"text": "Plants make food from light", "speed": 1.0},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert set(body) >= {"audio_b64", "word_timings", "duration_ms"}
    assert len(body["word_timings"]) == 5
    assert body["word_timings"][0]["word"] == "Plants"


def test_tts_word_contract(client, auth_headers):
    res = client.post("/tts/word", json={"word": "photosynthesis"}, headers=auth_headers)
    assert res.status_code == 200
    assert "audio_b64" in res.json()


def test_tts_service_rejects_empty_text():
    """Real service guard (not the fake): blank text is a 400, not a
    silent edge-tts call."""
    import asyncio
    from fastapi import HTTPException
    from backend.services import tts_service

    with pytest.raises(HTTPException) as exc:
        asyncio.run(tts_service.generate_tts("   "))
    assert exc.value.status_code == 400


# ── Reading: simplify / complexity / define / syllabify ─────────────
def test_simplify_contract(client, auth_headers):
    res = client.post(
        "/reading/simplify",
        json={"text": "Photosynthesis converts electromagnetic radiation."},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["simplified_text"] == FAKE_SIMPLIFIED
    for key in ("reading_level", "flesch_kincaid_grade", "original_hard_word_pct",
                "simplified_hard_word_pct", "changes_made"):
        assert key in body


def test_simplify_empty_text_400(client, auth_headers):
    res = client.post("/reading/simplify", json={"text": "   "}, headers=auth_headers)
    assert res.status_code == 400


def test_simplify_degrades_to_503_when_groq_fails(client, auth_headers, monkeypatch):
    """F42 fallback: an LLM outage is a 503 the UI can message, never a 500."""
    from backend.services import simplification_service

    # Restore the real simplify_text (fake_services replaced it), but
    # make the Groq client itself blow up.
    monkeypatch.setattr(simplification_service, "simplify_text", real_simplify_text)

    class Boom:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    raise RuntimeError("groq down")

    monkeypatch.setattr(simplification_service, "_client", lambda: Boom)
    res = client.post("/reading/simplify", json={"text": "Some text."}, headers=auth_headers)
    assert res.status_code == 503


def test_complexity_contract(client, auth_headers):
    text = "The cat sat on the mat. It was a sunny day."
    res = client.post("/reading/complexity", json={"text": text}, headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["word_count"] == 11
    assert body["sentence_count"] == 2
    assert set(body) >= {"flesch_kincaid_grade", "level_label", "hard_word_pct",
                         "est_reading_time_s"}


def test_complexity_empty_text_400(client, auth_headers):
    res = client.post("/reading/complexity", json={"text": ""}, headers=auth_headers)
    assert res.status_code == 400


class _FakeDictResponse:
    status_code = 200

    def json(self):
        return [{
            "word": "photosynthesis",
            "phonetic": "/ˌfəʊtəʊˈsɪnθəsɪs/",
            "meanings": [{
                "partOfSpeech": "noun",
                "definitions": [{
                    "definition": "The process by which plants make food from light.",
                    "example": "Leaves are the site of photosynthesis.",
                }],
            }],
        }]


class _FakeAsyncClient:
    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url):
        return _FakeDictResponse()


class _DownAsyncClient(_FakeAsyncClient):
    async def get(self, url):
        raise httpx.ConnectError("dictionaryapi.dev down")


def test_define_online_contract(client, auth_headers, monkeypatch):
    from backend.routers import reading

    monkeypatch.setattr(reading.httpx, "AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr(reading, "count_syllables", lambda w: 5)
    monkeypatch.setattr(reading, "split_syllables", lambda w: ("pho", "to", "syn", "the", "sis"))

    res = client.post("/reading/define", json={"word": "Photosynthesis"}, headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["word"] == "photosynthesis"
    assert body["source"] == "dictionaryapi"
    assert body["definition"].startswith("The process")
    assert body["example"]
    assert body["syllable_count"] == 5
    assert body["syllable_parts"] == ["pho", "to", "syn", "the", "sis"]
    assert body["meanings"][0]["partOfSpeech"] == "noun"


def test_define_falls_back_to_wordnet_when_offline(client, auth_headers, monkeypatch):
    from backend.routers import reading

    monkeypatch.setattr(reading.httpx, "AsyncClient", _DownAsyncClient)
    monkeypatch.setattr(reading, "count_syllables", lambda w: 1)
    monkeypatch.setattr(reading, "split_syllables", lambda w: ("cat",))
    monkeypatch.setattr(
        reading,
        "_wordnet_meanings",
        lambda word, max_per_pos=3: [
            {"partOfSpeech": "noun", "definitions": [{"definition": "feline mammal"}]}
        ],
    )

    res = client.post("/reading/define", json={"word": "cat"}, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["source"] == "wordnet"
    assert res.json()["definition"] == "feline mammal"


def test_define_empty_word_400(client, auth_headers):
    res = client.post("/reading/define", json={"word": "  "}, headers=auth_headers)
    assert res.status_code == 400


def test_syllabify_batch(client, auth_headers, monkeypatch):
    from backend.routers import reading

    monkeypatch.setattr(reading, "split_syllables", lambda w: tuple(w.lower().strip(".,")))
    res = client.post(
        "/reading/syllabify", json={"words": ["Cat,", "cat", "dog"]}, headers=auth_headers
    )
    assert res.status_code == 200
    # keyed by cleaned word, deduplicated
    assert set(res.json()["results"]) == {"cat", "dog"}


# ── real services (opt-in) ──────────────────────────────────────────
@pytest.mark.models
def test_real_syllable_counts():
    from backend.services.syllables import count_syllables

    assert count_syllables("cat") == 1
    assert count_syllables("photosynthesis") == 5
