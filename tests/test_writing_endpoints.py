"""
tests/test_writing_endpoints.py — Owner: M4
Phase 2 — NLP + Writing endpoints (M2: F21-F32, F48).
/nlp/* is DB-independent. /writing/* only uses saved_documents, whose
shape the migration keeps (it only gains a ForeignKey on user_id).
LanguageTool and DistilGPT-2 are faked; spaCy and the phonetic
checker run for real.
"""
import pytest


# ── /nlp/check ──────────────────────────────────────────────────────
def test_nlp_check_contract(client, auth_headers):
    res = client.post(
        "/nlp/check", json={"text": "I went their yesterday becuase it was nice."},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"spelling", "grammar", "homophones"}
    assert all(isinstance(body[k], list) for k in body)


def test_nlp_check_flags_misspelling(client, auth_headers):
    res = client.post("/nlp/check", json={"text": "I like becuase"}, headers=auth_headers)
    assert res.status_code == 200
    flagged = " ".join(str(item) for item in res.json()["spelling"]).lower()
    assert "becuase" in flagged


def test_nlp_check_empty_text_ok(client, auth_headers):
    res = client.post("/nlp/check", json={"text": ""}, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["spelling"] == []


# ── /nlp/predict ────────────────────────────────────────────────────
def test_nlp_predict_contract(client, auth_headers):
    res = client.post("/nlp/predict", json={"prefix": "At the end of"}, headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body["suggestions"], list)
    assert len(body["suggestions"]) <= 3
    assert isinstance(body["phrase_suggestion"], str)


# ── /writing/autosave ───────────────────────────────────────────────
def test_autosave_roundtrip(client, auth_headers):
    # brand-new user: empty draft, created on demand
    res = client.get("/writing/autosave", headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == {"content": ""}

    res = client.patch("/writing/autosave", json={"content": "Draft v1"}, headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == {"saved": True}

    client.patch("/writing/autosave", json={"content": "Draft v2"}, headers=auth_headers)
    assert client.get("/writing/autosave", headers=auth_headers).json() == {"content": "Draft v2"}


def test_autosave_draft_not_listed_as_document(client, auth_headers):
    client.patch("/writing/autosave", json={"content": "scratch"}, headers=auth_headers)
    assert client.get("/writing/documents", headers=auth_headers).json() == []


# ── /writing/documents CRUD ─────────────────────────────────────────
def test_documents_crud(client, auth_headers):
    res = client.post(
        "/writing/documents",
        json={"title": "My Essay", "content": "Once upon a time", "template": "essay"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    doc_id = res.json()["id"]

    listed = client.get("/writing/documents", headers=auth_headers).json()
    assert [d["id"] for d in listed] == [doc_id]
    assert listed[0]["title"] == "My Essay"

    full = client.get(f"/writing/documents/{doc_id}", headers=auth_headers).json()
    assert full["content"] == "Once upon a time"
    assert full["template"] == "essay"

    # B6: PUT updates in place, no new row
    res = client.put(
        f"/writing/documents/{doc_id}",
        json={"title": "My Essay (final)", "content": "The end", "template": "essay"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["id"] == doc_id
    listed = client.get("/writing/documents", headers=auth_headers).json()
    assert len(listed) == 1
    assert listed[0]["title"] == "My Essay (final)"

    res = client.delete(f"/writing/documents/{doc_id}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == {"deleted": True}
    assert client.get(f"/writing/documents/{doc_id}", headers=auth_headers).status_code == 404


def test_document_missing_id_404(client, auth_headers):
    for method in ("get", "delete"):
        res = getattr(client, method)("/writing/documents/does-not-exist", headers=auth_headers)
        assert res.status_code == 404
    res = client.put(
        "/writing/documents/does-not-exist",
        json={"title": "x", "content": "y"},
        headers=auth_headers,
    )
    assert res.status_code == 404


def test_template_used_logged(client, auth_headers):
    res = client.post("/writing/template-used", json={"template": "email"}, headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == {"logged": True}


# ── real models (opt-in) ────────────────────────────────────────────
@pytest.mark.models
def test_real_grammar_checker_runs():
    from backend.services.nlp_service import check_grammar

    issues = check_grammar("He go to school yesterday.")
    assert isinstance(issues, list)
    assert issues, "LanguageTool should flag 'He go'"


@pytest.mark.models
def test_real_prediction_returns_three_words():
    from backend.services.prediction_service import predict_phrase, predict_words

    words = predict_words("I would like to")
    assert 1 <= len(words) <= 3
    assert isinstance(predict_phrase("I would like to"), str)
