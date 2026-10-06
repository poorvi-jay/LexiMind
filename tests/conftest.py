"""
tests/conftest.py — Owner: M4
Shared fixtures for the LexiMind pytest suite.

DB-engine agnostic on purpose (M3's SQLite -> Postgres migration is in
flight, see M4 guide 3a). The app's real engine is never touched:
get_db is overridden with a throwaway engine built from
TEST_DATABASE_URL, and tables come from the ORM metadata, so the same
tests run against:

  * in-memory SQLite (default, no setup needed)
  * a real Postgres, e.g. the CI service container:
      TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/leximind_test

Heavy / networked services (EasyOCR, edge-tts, Groq, DistilGPT-2,
LanguageTool) are faked by default so the suite runs in seconds with no
API keys and no model downloads. Tests marked `models` exercise the real
ones and are skipped unless RUN_MODEL_TESTS=1.
"""
from __future__ import annotations

import os
import uuid

# auth.py raises at import if SECRET_KEY is missing, and main.py calls
# load_dotenv() — set test values first so a developer's backend/.env
# never leaks into the test run (load_dotenv does not override).
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Single place that knows where the ORM lives. If M3's migration renames
# models_temp.py, this is the only import to update.
try:
    import backend.models_temp as models
except ImportError:  # pragma: no cover - post-migration module name
    import backend.models as models  # type: ignore

Base = models.Base
get_db = models.get_db

from backend.main import app

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite://")
TEST_PASSWORD = "CorrectHorse9!"


# Markers (`models`, `m3_inflight`) are registered in pytest.ini.
def pytest_collection_modifyitems(config, items):
    if os.getenv("RUN_MODEL_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="real-model test; set RUN_MODEL_TESTS=1 to run")
    for item in items:
        if "models" in item.keywords:
            item.add_marker(skip)


# ── database ────────────────────────────────────────────────────────
def _make_engine():
    if TEST_DATABASE_URL.startswith("sqlite"):
        # StaticPool + check_same_thread=False: one shared in-memory DB
        # visible to TestClient's worker threads.
        return create_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(TEST_DATABASE_URL, pool_pre_ping=True)


@pytest.fixture(scope="session")
def engine():
    eng = _make_engine()
    yield eng
    eng.dispose()


@pytest.fixture()
def db_session_factory(engine):
    """Fresh schema per test — no state bleeds between tests."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    yield factory
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db(db_session_factory):
    """Direct DB handle for arranging state (e.g. backdating a word's
    next_review) that the public API deliberately doesn't expose."""
    session = db_session_factory()
    try:
        yield session
    finally:
        session.close()


# ── fake heavy services ─────────────────────────────────────────────
FAKE_OCR_TEXT = "The photosynthesis process converts sunlight into chemical energy"
FAKE_SIMPLIFIED = "Plants use sunlight to make food."


@pytest.fixture()
def fake_services(monkeypatch):
    """Replace every slow / networked dependency with a deterministic
    fake. Patched at the attribute the router actually calls."""
    from backend.services import ocr_service, simplification_service, tts_service
    from backend.routers import nlp as nlp_router

    async def fake_image(img_bytes: bytes) -> str:
        return FAKE_OCR_TEXT

    async def fake_pdf(pdf_bytes: bytes):
        return ["Page one text.", "Page two text."], 2

    async def fake_simplify(text: str) -> dict:
        return {
            "simplified_text": FAKE_SIMPLIFIED,
            "reading_level": "Easy",
            "flesch_kincaid_grade": 2.1,
            "original_hard_word_pct": 30.0,
            "simplified_hard_word_pct": 0.0,
            "changes_made": True,
        }

    async def fake_tts(text, speed=1.0, voice="en-GB-SoniaNeural", phrase_pauses=True):
        words = text.split()
        return {
            "audio_b64": "SUQzBAAAAAAA",  # "ID3" header, base64
            "word_timings": [
                {"word": w, "start_ms": i * 300, "end_ms": i * 300 + 280}
                for i, w in enumerate(words)
            ],
            "duration_ms": len(words) * 300,
        }

    async def fake_word_tts(word, voice="en-GB-SoniaNeural"):
        return {"audio_b64": "SUQzBAAAAAAA", "duration_ms": 400}

    monkeypatch.setattr(ocr_service, "extract_from_image", fake_image)
    monkeypatch.setattr(ocr_service, "extract_from_pdf", fake_pdf)
    monkeypatch.setattr(simplification_service, "simplify_text", fake_simplify)
    monkeypatch.setattr(tts_service, "generate_tts", fake_tts)
    monkeypatch.setattr(tts_service, "generate_word_tts", fake_word_tts)

    # nlp.py imports these by name, so patch the router's namespace.
    monkeypatch.setattr(nlp_router, "predict_words", lambda prefix: ["the", "a", "my"])
    monkeypatch.setattr(nlp_router, "predict_phrase", lambda prefix: "the end of the day")
    # LanguageTool needs a JVM + ~250 MB download; spaCy and the
    # phonetic checker are cheap and stay real.
    monkeypatch.setattr(
        nlp_router,
        "check_grammar",
        lambda text: [
            {"offset": 0, "length": 4, "message": "Fake grammar issue", "replacements": []}
        ],
    )
    return None


# ── client + auth ───────────────────────────────────────────────────
@pytest.fixture()
def client(db_session_factory, fake_services):
    def override_get_db():
        session = db_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    # No `with TestClient(...)`: that would run the lifespan -> init_db()
    # against the real dev.db. Schema comes from db_session_factory.
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def register_user(client):
    """Factory: register a fresh user, return {token, user, headers, email}."""

    def _register(name: str = "Test User", email: str | None = None,
                  password: str = TEST_PASSWORD) -> dict:
        email = email or f"user-{uuid.uuid4().hex[:10]}@example.com"
        res = client.post(
            "/auth/register",
            json={"name": name, "email": email, "password": password},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        return {
            "token": body["token"],
            "user": body["user"],
            "email": email,
            "password": password,
            "headers": {"Authorization": f"Bearer {body['token']}"},
        }

    return _register


@pytest.fixture()
def auth_headers(register_user):
    return register_user(name="Alice")["headers"]


@pytest.fixture()
def two_users(register_user):
    """Two independent accounts for cross-user isolation checks."""
    return register_user(name="Alice"), register_user(name="Bob")
