"""
tests/test_auth_matrix.py — Owner: M4
Phase 2 — "Every endpoint: a 401-without-token / 200-with-token pair."

Routes are discovered from the live FastAPI app, not hand-listed, so a
new endpoint added by any member without auth fails this file
immediately. To add a deliberately public route, put it in
PUBLIC_ROUTES; to give a new protected route its 200 case, add it to
HAPPY_PATH (test_happy_path_table_is_complete enforces that).
"""
import pytest

from backend.main import app

PUBLIC_ROUTES = {
    ("GET", "/health"),
    ("POST", "/auth/register"),
    ("POST", "/auth/login"),
}

# (method, path) -> request kwargs that should succeed for a fresh user.
# "{doc_id}" is filled in with a document created during the test.
HAPPY_PATH = {
    ("GET", "/auth/me"): {},
    ("PATCH", "/auth/me/preferences"): {"json": {"pref_dark_mode": True}},
    ("POST", "/ocr/image"): {"files": {"file": ("p.png", b"\x89PNG", "image/png")}},
    ("POST", "/ocr/pdf"): {"files": {"file": ("d.pdf", b"%PDF-1.4", "application/pdf")}},
    ("POST", "/tts/generate"): {"json": {"text": "Hello world"}},
    ("POST", "/tts/word"): {"json": {"word": "hello"}},
    ("POST", "/reading/simplify"): {"json": {"text": "Some hard text."}},
    ("POST", "/reading/complexity"): {"json": {"text": "The cat sat."}},
    ("POST", "/reading/syllabify"): {"json": {"words": []}},
    ("POST", "/reading/define"): None,  # needs network fakes — covered in test_reading_endpoints
    ("POST", "/classify"): {"json": {"words": ["cat"]}},
    ("POST", "/nlp/check"): {"json": {"text": "Hello there."}},
    ("POST", "/nlp/predict"): {"json": {"prefix": "Hello"}},
    ("GET", "/writing/autosave"): {},
    ("PATCH", "/writing/autosave"): {"json": {"content": "draft"}},
    ("GET", "/writing/documents"): {},
    ("POST", "/writing/documents"): {"json": {"title": "T", "content": "C"}},
    ("GET", "/writing/documents/{doc_id}"): {},
    ("PUT", "/writing/documents/{doc_id}"): {"json": {"title": "T2", "content": "C2"}},
    ("DELETE", "/writing/documents/{doc_id}"): {},
    ("POST", "/writing/template-used"): {"json": {"template": "essay"}},
    ("POST", "/sessions/reading"): {"json": {
        "total_words": 100, "hard_word_count": 5, "duration_seconds": 60,
        "source_type": "paste", "wpm": 100.0,
    }},
    ("POST", "/sessions/writing"): {"json": {"word_count": 50}},
    ("GET", "/analytics/summary"): {},
    ("GET", "/analytics/reading"): {},
    ("GET", "/analytics/writing"): {},
    ("GET", "/analytics/difficult-words"): {},
    ("GET", "/wordbank"): {},
    ("GET", "/wordbank/drill"): {},
    ("POST", "/wordbank/drill/result"): None,  # needs a word in the bank — covered in flows
    ("GET", "/wordbank/stats"): {},
    ("GET", "/wordbank/syllables"): {"params": {"word": "elephant"}},
}

def _app_routes():
    # Read from the OpenAPI schema rather than app.routes: newer FastAPI
    # versions nest included routers, and the schema is the public
    # contract anyway. (/docs, /openapi.json are excluded from it.)
    out = []
    for path, ops in app.openapi()["paths"].items():
        for method in ops:
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                out.append((method.upper(), path))
    return sorted(out)


ALL_ROUTES = _app_routes()
PROTECTED_ROUTES = [r for r in ALL_ROUTES if r not in PUBLIC_ROUTES]

# The 200 case for these hits tables M3's migration is re-keying, so it
# follows the m3_inflight convention. The 401 cases never reach the DB
# and stay blocking.
M3_INFLIGHT_PREFIXES = ("/sessions", "/analytics", "/wordbank")


def _happy_params():
    return [
        pytest.param(m, p, marks=pytest.mark.m3_inflight, id=f"{m} {p}")
        if p.startswith(M3_INFLIGHT_PREFIXES) else pytest.param(m, p, id=f"{m} {p}")
        for m, p in PROTECTED_ROUTES
    ]


def _concrete(path: str) -> str:
    return path.replace("{doc_id}", "some-doc-id")


def test_route_discovery_sanity():
    # If this drops, a router stopped being mounted in main.py.
    assert len(PROTECTED_ROUTES) >= 30, PROTECTED_ROUTES


def test_happy_path_table_is_complete():
    missing = set(PROTECTED_ROUTES) - set(HAPPY_PATH)
    assert not missing, f"New protected route(s) need a HAPPY_PATH entry: {sorted(missing)}"


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES, ids=lambda v: str(v))
def test_protected_route_rejects_missing_token(client, method, path):
    # No body on purpose: auth must fail (401) before body validation (422).
    res = client.request(method, _concrete(path))
    assert res.status_code == 401, f"{method} {path} -> {res.status_code}"


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES, ids=lambda v: str(v))
def test_protected_route_rejects_garbage_token(client, method, path):
    res = client.request(
        method, _concrete(path), headers={"Authorization": "Bearer not.a.jwt"}
    )
    assert res.status_code == 401


@pytest.mark.parametrize("method,path", _happy_params())
def test_protected_route_accepts_valid_token(client, auth_headers, method, path):
    kwargs = HAPPY_PATH[(method, path)]
    if kwargs is None:
        pytest.skip("200 case covered by a dedicated test (needs extra setup)")

    url = path
    if "{doc_id}" in path:
        created = client.post(
            "/writing/documents", json={"title": "Doc", "content": "x"}, headers=auth_headers
        )
        url = path.replace("{doc_id}", created.json()["id"])

    res = client.request(method, url, headers=auth_headers, **kwargs)
    assert res.status_code == 200, f"{method} {path} -> {res.status_code}: {res.text[:200]}"


@pytest.mark.parametrize("method,path", sorted(PUBLIC_ROUTES))
def test_public_routes_need_no_token(client, method, path):
    res = client.request(method, path, json={})
    assert res.status_code != 401
