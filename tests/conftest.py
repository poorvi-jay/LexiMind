"""
tests/conftest.py — Owner: M4
Shared fixtures for the LexiMind pytest suite.

The app is PostgreSQL-only since M3's migration (native UUID ids,
gen_random_uuid() defaults), so the tests run against a real, SEPARATE
Postgres test database:

    TEST_DATABASE_URL=postgresql+psycopg://leximind:PASSWORD@localhost:5432/leximind_test

That database is wiped at the start of the run and its tables are
emptied before every test. As a guard, its name must contain "test".
Never point it at your real leximind database.

The schema is built by M3's Alembic migrations (`alembic upgrade head`),
not by create_all, so the suite also proves the migrations apply cleanly
to an empty database.

Heavy / networked services (EasyOCR, edge-tts, Groq, DistilGPT-2,
LanguageTool) are faked by default so the suite runs in under a minute
with no API keys and no model downloads. Tests marked `models` exercise
the real ones and are skipped unless RUN_MODEL_TESTS=1.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "").strip()
TEST_PASSWORD = "CorrectHorse9!"

if not TEST_DATABASE_URL:
    pytest.exit(
        "TEST_DATABASE_URL is not set. Create a separate test database, e.g.\n"
        "  CREATE DATABASE leximind_test OWNER leximind;\n"
        "then run:\n"
        "  TEST_DATABASE_URL=postgresql+psycopg://leximind:PASSWORD@localhost:5432/"
        "leximind_test pytest",
        returncode=2,
    )
if "test" not in TEST_DATABASE_URL.rsplit("/", 1)[-1].lower():
    pytest.exit(
        "Refusing to run: the database name in TEST_DATABASE_URL must contain 'test' "
        "(the suite wipes it).",
        returncode=2,
    )

# Must happen before anything imports backend.*:
#   - models_temp.py builds its engine from DATABASE_URL at import, so
#     the app itself now talks to the test database.
#   - auth.py raises at import if SECRET_KEY is missing.
#   - main.py / alembic env.py call load_dotenv(), which never overrides
#     variables that are already set, so backend/.env can't leak in.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("OCR_PREWARM", "0")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

# Single place that knows where the ORM lives. If models_temp.py is
# ever renamed, this is the only import to update.
try:
    import backend.models_temp as models  # noqa: E402
except ImportError:  # pragma: no cover - future module name
    import backend.models as models  # type: ignore  # noqa: E402

from backend.main import app  # noqa: E402


# The `models` marker is registered in pytest.ini.
def pytest_collection_modifyitems(config, items):
    if os.getenv("RUN_MODEL_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="real-model test; set RUN_MODEL_TESTS=1 to run")
    for item in items:
        if "models" in item.keywords:
            item.add_marker(skip)


# ── database ────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def migrated_db():
    """Wipe the test database once, then build it with the real
    Alembic migrations (the same `alembic upgrade head` Railway runs)."""
    with models.engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    command.upgrade(Config(str(REPO_ROOT / "alembic.ini")), "head")
    yield models.engine
    models.engine.dispose()


@pytest.fixture()
def clean_db(migrated_db):
    """Empty every app table before each test (alembic_version stays)."""
    tables = [t.name for t in models.Base.metadata.sorted_tables]
    with migrated_db.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture()
def db(clean_db):
    """Direct DB handle for arranging state (e.g. backdating a word's
    next_review) that the public API deliberately doesn't expose."""
    session = models.SessionLocal()
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
def client(clean_db, fake_services):
    # `with` runs the app's lifespan, so init_db()'s "schema exists"
    # check is exercised on every test too.
    with TestClient(app) as test_client:
        yield test_client


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
