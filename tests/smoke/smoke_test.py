"""
tests/smoke/smoke_test.py — Owner: M4
Phase 8 — end-to-end smoke test against a DEPLOYED backend (real models,
real Groq / edge-tts, real database). Not collected by pytest.

Follows the deploy checklist path:
  register -> login -> upload image -> simplify -> TTS -> word prediction
  (3 + phrase pill) -> drill a word -> badge appears -> analytics populated

Usage:
  python tests/smoke/smoke_test.py --api https://<railway-app>.up.railway.app \
      --origin https://<vercel-app>.vercel.app
  python tests/smoke/smoke_test.py --api http://127.0.0.1:8000 --skip ocr simplify

Each run registers a fresh smoke+<timestamp>@example.com account (no
delete-account endpoint exists, so these accumulate — filter them out of
any real-user reporting). Exit code 0 = all non-skipped steps passed.
"""
from __future__ import annotations

import argparse
import io
import sys
import time
import uuid

import httpx

STEPS = [
    "health", "cors", "register", "login", "me", "ocr", "complexity", "classify",
    "simplify", "define", "tts", "nlp_check", "predict", "reading_sessions",
    "wordbank", "drill", "writing_session", "analytics", "isolation",
]

SENTENCE_20 = (
    "The quick brown fox jumps over the lazy dog while seven curious children "
    "watch quietly from the old wooden bridge"
)


class Smoke:
    def __init__(self, api: str, origin: str | None, skip: set[str], timeout: float):
        self.api = api.rstrip("/")
        self.origin = origin.rstrip("/") if origin else None
        self.skip = skip
        self.http = httpx.Client(base_url=self.api, timeout=timeout)
        self.headers: dict[str, str] = {}
        self.email = f"smoke+{int(time.time())}-{uuid.uuid4().hex[:6]}@example.com"
        self.password = "Smoke-Test-" + uuid.uuid4().hex[:10]
        self.ocr_text = SENTENCE_20
        self.results: list[tuple[str, str, float, str]] = []

    # ── helpers ─────────────────────────────────────────────────────
    def call(self, method, path, expect=200, **kw):
        kw.setdefault("headers", self.headers)
        res = self.http.request(method, path, **kw)
        if res.status_code != expect:
            raise AssertionError(f"{method} {path} -> {res.status_code} (want {expect}): "
                                 f"{res.text[:300]}")
        return res.json() if res.content else None

    def run(self):
        for name in STEPS:
            if name in self.skip:
                self.results.append((name, "SKIP", 0.0, ""))
                continue
            start = time.time()
            try:
                note = getattr(self, f"step_{name}")() or ""
                self.results.append((name, "PASS", time.time() - start, note))
            except Exception as exc:  # keep going; report everything
                self.results.append((name, "FAIL", time.time() - start,
                                     f"{type(exc).__name__}: {exc}"))
                if name in ("register", "login"):
                    break  # nothing after this can work
        return self.report()

    def report(self) -> int:
        width = max(len(n) for n in STEPS)
        print(f"\nLexiMind smoke test — {self.api}\n")
        for name, status, secs, note in self.results:
            print(f"  {status:4}  {name:<{width}}  {secs:6.2f}s  {note}")
        failed = [r for r in self.results if r[1] == "FAIL"]
        print(f"\n{len(failed)} failed, "
              f"{sum(r[1] == 'PASS' for r in self.results)} passed, "
              f"{sum(r[1] == 'SKIP' for r in self.results)} skipped\n")
        return 1 if failed else 0

    # ── steps ───────────────────────────────────────────────────────
    def step_health(self):
        body = self.call("GET", "/health", headers={})
        assert body["status"] == "ok", body
        return f"version {body.get('version')}"

    def step_cors(self):
        if not self.origin:
            return "no --origin given; skipped check"
        res = self.http.options(
            "/auth/login",
            headers={"Origin": self.origin, "Access-Control-Request-Method": "POST",
                     "Access-Control-Request-Headers": "content-type,authorization"},
        )
        allowed = res.headers.get("access-control-allow-origin")
        assert allowed == self.origin, (
            f"CORS_ORIGINS on Railway doesn't include {self.origin} (got {allowed!r})")
        return "preflight ok"

    def step_register(self):
        body = self.call("POST", "/auth/register", headers={},
                         json={"name": "Smoke Test", "email": self.email,
                               "password": self.password})
        self.headers = {"Authorization": f"Bearer {body['token']}"}
        self.user_id = body["user"]["id"]
        self.call("POST", "/auth/register", expect=409, headers={},
                  json={"name": "Dup", "email": self.email, "password": self.password})
        return self.email

    def step_login(self):
        self.call("POST", "/auth/login", expect=401, headers={},
                  json={"email": self.email, "password": "wrong-password"})
        body = self.call("POST", "/auth/login", headers={},
                         json={"email": self.email, "password": self.password})
        self.headers = {"Authorization": f"Bearer {body['token']}"}

    def step_me(self):
        self.call("GET", "/auth/me", expect=401, headers={})
        assert self.call("GET", "/auth/me")["email"] == self.email
        body = self.call("PATCH", "/auth/me/preferences", json={"pref_dark_mode": True})
        assert body["pref_dark_mode"] is True

    def step_ocr(self):
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGB", (1400, 160), "white")
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default(size=44)
        draw.text((20, 50), "Plants use photosynthesis to make food", fill="black", font=font)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        body = self.call("POST", "/ocr/image",
                         files={"file": ("smoke.png", buf.getvalue(), "image/png")})
        text = body["text"].lower()
        assert "photosynthesis" in text or "plants" in text, body
        self.ocr_text = body["text"]
        return repr(body["text"][:60])

    def step_complexity(self):
        body = self.call("POST", "/reading/complexity", json={"text": SENTENCE_20})
        assert body["word_count"] == 20, body

    def step_classify(self):
        words = ["cat", "photosynthesis", "electroencephalography"]
        res = self.call("POST", "/classify", json={"words": words})["results"]
        assert [r["word"] for r in res] == words
        assert all(set(r) == {"word", "label", "confidence"} for r in res)
        assert res[2]["label"] == "Hard", res
        return ", ".join(f"{r['word']}={r['label']}" for r in res)

    def step_simplify(self):
        body = self.call("POST", "/reading/simplify",
                         json={"text": "Photosynthesis is the biochemical process whereby "
                                       "chlorophyll-containing organisms synthesise carbohydrates."})
        assert body["simplified_text"], body
        return body["reading_level"]

    def step_define(self):
        body = self.call("POST", "/reading/define", json={"word": "photosynthesis"})
        assert body["definition"], body
        return f"source={body['source']} syllables={body['syllable_count']}"

    def step_tts(self):
        body = self.call("POST", "/tts/generate", json={"text": SENTENCE_20, "speed": 1.0})
        timings = body["word_timings"]
        assert len(timings) == 20, f"{len(timings)} timings for 20 words"
        starts = [t["start_ms"] for t in timings]
        assert starts == sorted(starts), "word timings not monotonic"
        # Server-side proxy for the <150ms drift check; the real check is
        # by eye/ear in the browser (README deploy checklist).
        last_end = timings[-1]["end_ms"]
        assert last_end <= body["duration_ms"] + 150, (last_end, body["duration_ms"])
        self.call("POST", "/tts/word", json={"word": "photosynthesis"})
        return f"{body['duration_ms']} ms audio"

    def step_nlp_check(self):
        body = self.call("POST", "/nlp/check",
                         json={"text": "I went their yesterday becuase it was nice."})
        assert set(body) == {"spelling", "grammar", "homophones"}
        assert body["spelling"], "phonetic checker missed 'becuase'"
        return f"{len(body['spelling'])} spelling, {len(body['grammar'])} grammar, " \
               f"{len(body['homophones'])} homophone"

    def step_predict(self):
        body = self.call("POST", "/nlp/predict", json={"prefix": "At the end of the"})
        assert len(body["suggestions"]) == 3, body
        assert body["phrase_suggestion"], "phrase pill would not appear"
        return f"{body['suggestions']} + '{body['phrase_suggestion']}'"

    def step_reading_sessions(self):
        session = {"wpm": 110.0, "total_words": 20, "hard_word_count": 1,
                   "repeat_count": 1, "duration_seconds": 45, "source_type": "paste",
                   "simplified": False, "complexity_score": 5.0,
                   "words": [{"word": "smokeverbosity", "label": "Hard"}]}
        for _ in range(3):  # 3 repeats -> auto-added to the word bank
            assert self.call("POST", "/sessions/reading", json=session)["logged"] is True

    def step_wordbank(self):
        stats = self.call("GET", "/wordbank/stats")
        assert stats["due_count"] >= 1, f"drill-due badge would not appear: {stats}"
        bank = self.call("GET", "/wordbank")
        assert any(w["word"] == "smokeverbosity" for w in bank), bank
        return f"badge due_count={stats['due_count']}"

    def step_drill(self):
        drill = self.call("GET", "/wordbank/drill")
        assert any(w["word"] == "smokeverbosity" for w in drill), drill
        self.call("GET", "/wordbank/syllables", params={"word": "smokeverbosity"})
        body = self.call("POST", "/wordbank/drill/result",
                         json={"word": "smokeverbosity", "quality": 4})
        assert body["sm2_repetitions"] == 1 and body["total_drills"] == 1, body
        return f"next_review {body['next_review']}"

    def step_writing_session(self):
        self.call("PATCH", "/writing/autosave", json={"content": "smoke draft"})
        assert self.call("GET", "/writing/autosave")["content"] == "smoke draft"
        doc = self.call("POST", "/writing/documents",
                        json={"title": "Smoke doc", "content": "hello", "template": "essay"})
        self.doc_id = doc["id"]
        self.call("POST", "/sessions/writing",
                  json={"word_count": 10, "spell_error_count": 1})

    def step_analytics(self):
        summary = self.call("GET", "/analytics/summary")
        assert summary["total_sessions"] == 3, summary
        assert self.call("GET", "/analytics/reading"), "reading history empty"
        assert self.call("GET", "/analytics/writing"), "writing history empty"
        words = self.call("GET", "/analytics/difficult-words")
        assert words and words[0]["word"] == "smokeverbosity", words
        return f"avg_wpm={summary['avg_wpm']}"

    def step_isolation(self):
        other = self.call("POST", "/auth/register", headers={}, json={
            "name": "Smoke Other", "email": "other-" + self.email, "password": self.password})
        h = {"Authorization": f"Bearer {other['token']}"}
        assert self.call("GET", "/analytics/summary", headers=h)["total_sessions"] == 0
        assert self.call("GET", "/wordbank", headers=h) == []
        assert self.call("GET", "/writing/documents", headers=h) == []
        if getattr(self, "doc_id", None):
            self.call("GET", f"/writing/documents/{self.doc_id}", expect=404, headers=h)
        return "second account sees nothing"


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", required=True, help="backend base URL")
    parser.add_argument("--origin", help="frontend origin to check CORS for")
    parser.add_argument("--skip", nargs="*", default=[], choices=STEPS)
    parser.add_argument("--timeout", type=float, default=120.0,
                        help="per-request seconds (first OCR / predict call can be slow)")
    args = parser.parse_args()
    sys.exit(Smoke(args.api, args.origin, set(args.skip), args.timeout).run())


if __name__ == "__main__":
    main()
