"""
tests/test_security_isolation.py — Owner: M4
Phase 4 — two-account cross-user data leakage checks + token abuse.
Formalises the pattern M2 and M3 proved manually: every per-user query
is scoped to current_user.id, and another user's ids return 404, never
their data.

Writing (saved_documents) checks are blocking. Sessions/Analytics/Word
Bank checks are m3_inflight — and worth re-running the moment the
migration lands, since it rewrites exactly these user_id columns.
"""
from datetime import datetime, timedelta

import pytest
from jose import jwt

from backend.routers.auth import ALGORITHM, SECRET_KEY
from tests.conftest import models


# ── token abuse ─────────────────────────────────────────────────────
def _token(sub, exp_delta=timedelta(hours=1), key=SECRET_KEY, alg=ALGORITHM):
    payload = {"exp": datetime.utcnow() + exp_delta}
    if sub is not None:
        payload["sub"] = sub
    return jwt.encode(payload, key, algorithm=alg)


def _get_me(client, token):
    return client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})


def test_expired_token_rejected(client, register_user):
    uid = register_user()["user"]["id"]
    assert _get_me(client, _token(uid, exp_delta=timedelta(seconds=-5))).status_code == 401


def test_token_signed_with_wrong_key_rejected(client, register_user):
    uid = register_user()["user"]["id"]
    assert _get_me(client, _token(uid, key="attacker-key")).status_code == 401


def test_unsigned_alg_none_token_rejected(client, register_user):
    import base64
    import json

    uid = register_user()["user"]["id"]

    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    forged = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': uid})}."
    assert _get_me(client, forged).status_code == 401


def test_token_without_sub_rejected(client):
    assert _get_me(client, _token(None)).status_code == 401


def test_token_for_deleted_user_rejected(client, register_user, db):
    u = register_user()
    db.query(models.User).filter(models.User.id == u["user"]["id"]).delete()
    db.commit()
    assert _get_me(client, u["token"]).status_code == 401


def test_token_for_other_user_id_only_sees_that_user(client, two_users):
    alice, bob = two_users
    assert _get_me(client, alice["token"]).json()["id"] == alice["user"]["id"]
    assert _get_me(client, bob["token"]).json()["id"] == bob["user"]["id"]


def test_login_error_does_not_reveal_which_field_was_wrong(client, register_user):
    u = register_user()
    wrong_pw = client.post("/auth/login", json={"email": u["email"], "password": "nope-nope"})
    no_user = client.post("/auth/login",
                          json={"email": "ghost@example.com", "password": "nope-nope"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


def test_preferences_cannot_overwrite_identity_fields(client, auth_headers):
    before = client.get("/auth/me", headers=auth_headers).json()
    client.patch(
        "/auth/me/preferences",
        json={"id": "hijack", "email": "evil@example.com", "pref_dark_mode": True},
        headers=auth_headers,
    )
    after = client.get("/auth/me", headers=auth_headers).json()
    assert after["id"] == before["id"]
    assert after["email"] == before["email"]


# ── writing: saved_documents isolation (blocking) ───────────────────
def test_documents_isolated_between_users(client, two_users):
    alice, bob = two_users
    doc_id = client.post(
        "/writing/documents",
        json={"title": "Alice private", "content": "secret diary"},
        headers=alice["headers"],
    ).json()["id"]

    assert client.get("/writing/documents", headers=bob["headers"]).json() == []
    assert client.get(f"/writing/documents/{doc_id}", headers=bob["headers"]).status_code == 404
    assert client.put(f"/writing/documents/{doc_id}", json={"title": "pwned", "content": ""},
                      headers=bob["headers"]).status_code == 404
    assert client.delete(f"/writing/documents/{doc_id}",
                         headers=bob["headers"]).status_code == 404

    # Alice's doc is untouched by Bob's attempts
    doc = client.get(f"/writing/documents/{doc_id}", headers=alice["headers"]).json()
    assert doc["title"] == "Alice private"
    assert doc["content"] == "secret diary"


def test_autosave_draft_isolated_between_users(client, two_users):
    alice, bob = two_users
    client.patch("/writing/autosave", json={"content": "alice draft"}, headers=alice["headers"])
    client.patch("/writing/autosave", json={"content": "bob draft"}, headers=bob["headers"])
    assert client.get("/writing/autosave", headers=alice["headers"]).json()["content"] \
        == "alice draft"
    assert client.get("/writing/autosave", headers=bob["headers"]).json()["content"] \
        == "bob draft"


def test_preferences_isolated_between_users(client, two_users):
    alice, bob = two_users
    client.patch("/auth/me/preferences", json={"pref_font_size": 30}, headers=alice["headers"])
    assert client.get("/auth/me", headers=bob["headers"]).json()["pref_font_size"] == 18


# ── sessions / analytics / word bank isolation (m3_inflight) ────────
def _hard_session(word):
    return {"total_words": 50, "hard_word_count": 1, "duration_seconds": 60,
            "source_type": "paste", "wpm": 90.0,
            "words": [{"word": word, "label": "Hard"}]}


@pytest.mark.m3_inflight
def test_analytics_isolated_between_users(client, two_users):
    alice, bob = two_users
    for _ in range(2):
        client.post("/sessions/reading", json=_hard_session("alicesword"),
                    headers=alice["headers"])
    client.post("/sessions/writing", json={"word_count": 10}, headers=alice["headers"])

    assert client.get("/analytics/summary", headers=bob["headers"]).json()["total_sessions"] == 0
    for path in ("/analytics/reading", "/analytics/writing", "/analytics/difficult-words"):
        assert client.get(path, headers=bob["headers"]).json() == [], path


@pytest.mark.m3_inflight
def test_word_repeat_counts_are_per_user(client, two_users):
    """Same word, two users: counts must not merge across accounts."""
    alice, bob = two_users
    for _ in range(2):
        client.post("/sessions/reading", json=_hard_session("shared"), headers=alice["headers"])
    client.post("/sessions/reading", json=_hard_session("shared"), headers=bob["headers"])

    a = client.get("/analytics/difficult-words", headers=alice["headers"]).json()
    b = client.get("/analytics/difficult-words", headers=bob["headers"]).json()
    assert a[0]["repeat_count"] == 2
    assert b[0]["repeat_count"] == 1
    # Bob's 3rd global repeat must NOT have put the word in anyone's bank
    assert client.get("/wordbank", headers=alice["headers"]).json() == []
    assert client.get("/wordbank", headers=bob["headers"]).json() == []


@pytest.mark.m3_inflight
def test_wordbank_isolated_between_users(client, two_users):
    alice, bob = two_users
    for _ in range(3):
        client.post("/sessions/reading", json=_hard_session("ubiquitous"),
                    headers=alice["headers"])
    assert len(client.get("/wordbank", headers=alice["headers"]).json()) == 1

    assert client.get("/wordbank", headers=bob["headers"]).json() == []
    assert client.get("/wordbank/drill", headers=bob["headers"]).json() == []
    assert client.get("/wordbank/stats", headers=bob["headers"]).json() == {
        "due_count": 0, "total_words": 0,
    }
    # Bob can't drill (and so can't mutate SM-2 state of) Alice's word
    res = client.post("/wordbank/drill/result", json={"word": "ubiquitous", "quality": 5},
                      headers=bob["headers"])
    assert res.status_code == 404
    entry = client.get("/wordbank", headers=alice["headers"]).json()[0]
    assert entry["total_drills"] == 0
    assert entry["sm2_repetitions"] == 0
