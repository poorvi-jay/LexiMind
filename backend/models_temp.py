"""
DATABASE MODELS
===============

This module contains the SQLAlchemy models used by LexiMind,
including users, saved documents, writing sessions, reading
sessions, and word-repeat logs.

The database is PostgreSQL, configured through the DATABASE_URL
environment variable (see backend/.env.example). If DATABASE_URL is
not set, a local SQLite file (backend/dev.db) is used instead so the
app still starts for quick local experiments.

Tables are created on startup by init_db(). create_all() only creates
missing tables - it does not alter existing ones - so column changes
need a manual migration on an existing database.

STATUS: ACTIVE
"""

import os
import uuid
import logging
import datetime

from dotenv import load_dotenv

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    DateTime,
    Float,
    Date,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100))
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.UTC),
    )

    # Preference columns — mirrors M1's accessibility settings so
    # Auth (F03/F04) can persist them server-side instead of
    # localStorage (per Handover Section 7's known-issue note).
    # Add more pref_* columns here as needed, matching PRD Section 4.
    pref_font = Column(String(50), default="Arial")
    pref_overlay = Column(String(7), default="#FFFFFF")
    pref_font_size = Column(Integer, default=18)
    pref_dark_mode = Column(Boolean, default=False)


class SavedDocument(Base):
    __tablename__ = "saved_documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    title = Column(String(150), default="Untitled Draft")
    content = Column(Text, default="")
    template = Column(String(50), nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.UTC),
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )
    is_draft = Column(Boolean, default=False)


class WritingSession(Base):
    __tablename__ = "writing_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    date = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.UTC),
    )
    word_count = Column(Integer, default=0)
    spell_error_count = Column(Integer, default=0)
    grammar_error_count = Column(Integer, default=0)
    homophone_flag_count = Column(Integer, default=0)
    template_used = Column(String(50), nullable=True)


class ReadingSession(Base):
    __tablename__ = "reading_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    date = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.UTC),
    )
    wpm = Column(Float)
    total_words = Column(Integer)
    hard_word_count = Column(Integer)
    repeat_count = Column(Integer)
    duration_seconds = Column(Integer)
    source_type = Column(String(10))  # 'image' | 'pdf' | 'paste'
    simplified = Column(Boolean)
    complexity_score = Column(Float)


class WordRepeatLog(Base):
    __tablename__ = "word_repeat_log"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    word = Column(String(100))
    repeat_count = Column(Integer, default=0)
    difficulty_label = Column(String(10))
    last_seen = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.UTC),
    )


class WordBank(Base):
    __tablename__ = "word_bank"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    word = Column(String(100))
    difficulty_label = Column(String(10))
    sm2_ef = Column(Float, default=2.5)
    sm2_interval = Column(Integer, default=1)
    sm2_repetitions = Column(Integer, default=0)
    next_review = Column(Date)
    total_drills = Column(Integer, default=0)
    last_quality = Column(Integer)
    added_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.UTC),
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "word",
            name="uq_wordbank_user_word",
        ),
    )


load_dotenv()

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_PATH = os.path.join(_BASE_DIR, "dev.db")


def _normalize_database_url(url: str) -> str:
    """Point postgres URLs at the psycopg (v3) driver. Hosting
    providers often hand out postgres:// or postgresql:// URLs, which
    SQLAlchemy would otherwise map to psycopg2."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def make_engine(url: str):
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(
        url,
        pool_pre_ping=True,
        # DateTime columns store UTC without a timezone. Pinning the
        # session to UTC stops Postgres from shifting timestamps into
        # the server's local timezone.
        connect_args={"options": "-c timezone=utc"},
    )


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL:
    DATABASE_URL = _normalize_database_url(DATABASE_URL)
else:
    DATABASE_URL = f"sqlite:///{SQLITE_PATH}"
    logger.warning(
        "DATABASE_URL is not set - using local SQLite at %s. "
        "Set DATABASE_URL in backend/.env to use PostgreSQL.",
        SQLITE_PATH,
    )

engine = make_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def init_db():
    """Create all tables if they don't already exist. Called once at
    app startup in main.py — safe to call repeatedly, no-op if tables
    already exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session, always closed after
    the request completes, even if an exception occurs."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()