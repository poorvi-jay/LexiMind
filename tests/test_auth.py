"""
tests/test_auth.py — Owner: M4
Phase 2 — Auth endpoints (F01-F04, AC-01/AC-02).
DB-independent in the sense that matters: only the users table, which
M3's migration keeps as the FK target, not reshapes.
"""
from datetime import datetime, timedelta

from jose import jwt

from tests.conftest import TEST_PASSWORD, models


def test_register_returns_token_and_user(client):
    res = client.post(
        "/auth/register",
        json={"name": "Alice", "email": "alice@example.com", "password": TEST_PASSWORD},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["token"]
    user = body["user"]
    assert user["email"] == "alice@example.com"
    assert user["name"] == "Alice"
    # Default accessibility prefs are populated server-side
    assert user["pref_font"] == "Arial"
    assert user["pref_font_size"] == 18
    assert user["pref_dark_mode"] is False
    assert "password_hash" not in user
    assert "password" not in user


def test_register_duplicate_email_returns_409(client, register_user):
    existing = register_user(email="dup@example.com")
    res = client.post(
        "/auth/register",
        json={"name": "Again", "email": existing["email"], "password": TEST_PASSWORD},
    )
    assert res.status_code == 409


def test_register_rejects_short_password(client):
    res = client.post(
        "/auth/register",
        json={"name": "Short", "email": "short@example.com", "password": "abc"},
    )
    assert res.status_code == 422


def test_register_rejects_invalid_email(client):
    res = client.post(
        "/auth/register",
        json={"name": "Bad", "email": "not-an-email", "password": TEST_PASSWORD},
    )
    assert res.status_code == 422


def test_login_success(client, register_user):
    u = register_user()
    res = client.post("/auth/login", json={"email": u["email"], "password": u["password"]})
    assert res.status_code == 200
    body = res.json()
    assert body["token"]
    assert body["user"]["id"] == u["user"]["id"]


def test_login_wrong_password_returns_401(client, register_user):
    u = register_user()
    res = client.post("/auth/login", json={"email": u["email"], "password": "wrong-password"})
    assert res.status_code == 401


def test_login_unknown_email_returns_401(client):
    res = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": TEST_PASSWORD}
    )
    assert res.status_code == 401


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_returns_current_user(client, register_user):
    u = register_user(name="Carol")
    res = client.get("/auth/me", headers=u["headers"])
    assert res.status_code == 200
    assert res.json()["email"] == u["email"]
    assert res.json()["name"] == "Carol"


def test_preferences_partial_update(client, auth_headers):
    # Real path is /auth/me/preferences (PRD text says /auth/preferences —
    # deliberate, see M4 guide section 5).
    res = client.patch(
        "/auth/me/preferences", json={"pref_dark_mode": True}, headers=auth_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body["pref_dark_mode"] is True
    # Fields not sent are untouched
    assert body["pref_font"] == "Arial"
    assert body["pref_font_size"] == 18

    res = client.patch(
        "/auth/me/preferences",
        json={"pref_font": "OpenDyslexic", "pref_font_size": 22, "pref_overlay": "#FFF5CC"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["pref_font"] == "OpenDyslexic"
    assert body["pref_font_size"] == 22
    assert body["pref_overlay"] == "#FFF5CC"
    assert body["pref_dark_mode"] is True  # persisted from the first call

    # And it's really persisted, not just echoed
    me = client.get("/auth/me", headers=auth_headers).json()
    assert me["pref_font"] == "OpenDyslexic"


def test_preferences_requires_token(client):
    assert client.patch("/auth/me/preferences", json={"pref_dark_mode": True}).status_code == 401


def test_token_payload_has_sub_and_24h_expiry(client, register_user):
    from backend.routers.auth import ALGORITHM, SECRET_KEY

    u = register_user()
    payload = jwt.decode(u["token"], SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == u["user"]["id"]
    ttl = datetime.utcfromtimestamp(payload["exp"]) - datetime.utcnow()
    assert timedelta(hours=23) < ttl <= timedelta(hours=24)


def test_password_is_stored_hashed(client, register_user, db):
    u = register_user()
    row = db.query(models.User).filter(models.User.email == u["email"]).one()
    assert row.password_hash != u["password"]
    assert row.password_hash.startswith("$2")  # bcrypt
