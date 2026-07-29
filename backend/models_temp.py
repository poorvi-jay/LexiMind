"""
TEMPORARY DATABASE MODELS — Owner: M2
====================================
This file is a STOPGAP, not the final schema.

Per Build Guide Section 4.1: this holds a minimal `users` table
(email, password hash, pref_* columns) so Authentication isn't
blocked while waiting for the real 6-table schema (PRD Section 4).

When the full schema lands, this file's `User` model gets merged
into it and this file is deleted. Do not build permanent
functionality on top of it without expecting that migration.
Avoid SQLite-specific raw SQL anywhere in the app, since this will
eventually migrate to Postgres.

STATUS: IMPLEMENTED (Task 6) — users table + SQLite connection.
"""
import os
import uuid
import datetime

from sqlalchemy import Column, String, Boolean, Integer, DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100))
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

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
    content = Column(String(50000), default="")
    template = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    is_draft = Column(Boolean, default=False)


class WritingSession(Base):
    __tablename__ = "writing_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    date = Column(DateTime, default=datetime.datetime.utcnow)
    word_count = Column(Integer, default=0)
    spell_error_count = Column(Integer, default=0)
    grammar_error_count = Column(Integer, default=0)
    homophone_flag_count = Column(Integer, default=0)
    template_used = Column(String(50), nullable=True)
    
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_PATH = os.path.join(_BASE_DIR, "dev.db")

engine = create_engine(
    f"sqlite:///{_DB_PATH}", connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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