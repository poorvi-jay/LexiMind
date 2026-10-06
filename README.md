# LexiMind

Reading and writing support for dyslexic users: OCR → simplify → word-synced TTS
reading, a writing notepad with phonetic spell check and prediction, an ML word-
difficulty classifier, session analytics, and an SM-2 Word Bank.

| Layer    | Stack                                | Deploy                         |
|----------|--------------------------------------|--------------------------------|
| Frontend | React 19 + Vite (`frontend/`)        | Vercel (`vercel.json`)         |
| Backend  | FastAPI (`backend/`)                 | Railway (`Dockerfile`, `railway.toml`) |
| Database | SQLite today → Postgres (M3, in flight) | Railway Postgres addon      |

The word classifier is trained on **CompLex 2.0** (CC-BY 4.0, MMU-TDMLab/CompLex),
not the MRC Psycholinguistic Database the PRD originally named.

## Development setup

Python 3.13.x, Node.js 22.x.

```bash
python3.13 -m venv .venv && source .venv/bin/activate   # Windows: py -3.13 -m venv .venv
pip install -r requirements.txt
# create backend/.env with SECRET_KEY and GROQ_API_KEY (see "Environment variables")
uvicorn backend.main:app --reload

cd frontend
npm install
npm run dev
```

If the DistilGPT-2 download stalls or 404s, it's Hugging Face Xet:
`export HF_HUB_DISABLE_XET=1 && pip uninstall -y hf-xet`.

## Tests

```bash
pip install -r tests/requirements-test.txt
pytest                                 # whole suite, in-memory SQLite, ~40 s
pytest -m "not m3_inflight"            # what CI treats as blocking today
pytest -m m3_inflight                  # Sessions / Analytics / Word Bank
RUN_MODEL_TESTS=1 pytest -m models     # real LanguageTool / DistilGPT-2 / CMUdict
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/leximind_test pytest
```

| File | Covers |
|------|--------|
| `tests/test_auth.py` | register / login / `/auth/me` / `/auth/me/preferences` (the PRD's `/auth/preferences` is deliberately `/auth/me/preferences`) |
| `tests/test_reading_endpoints.py` | `/ocr/image`, `/ocr/pdf`, `/tts/generate`, `/tts/word`, `/reading/simplify\|complexity\|define\|syllabify` |
| `tests/test_writing_endpoints.py` | `/nlp/check`, `/nlp/predict`, `/writing/autosave`, `/writing/documents*`, `/writing/template-used` |
| `tests/test_classify.py` | `/classify` `{results:[{word,label,confidence}]}` contract with the real model, plus a **Hard-recall ≥ 85%** gate (AC-26's 80% overall accuracy isn't met, 63.6%, which M3 disclosed, so the gate is on Hard-recall) |
| `tests/test_auth_matrix.py` | Reads every route from the live OpenAPI schema and checks each one with no token (401), a garbage token (401) and a valid token (200). A new endpoint without auth fails CI. |
| `tests/test_sessions_analytics_wordbank.py` | `/sessions/*`, `/analytics/*`, `/wordbank*`, SM-2 for qualities 1/3/4/5 (`m3_inflight`) |
| `tests/test_regression_flows.py` | Reading, Writing, Analytics and Word Bank flows end to end (Analytics and Word Bank are `m3_inflight`) |
| `tests/test_security_isolation.py` | Two-account cross-user leakage checks; expired, forged, `alg:none` and deleted-user tokens |
| `tests/smoke/smoke_test.py` | Post-deploy smoke test against a real URL (not collected by pytest) |

How the tests are built:
- `conftest.py` overrides `get_db` with a throwaway engine and builds the schema from the
  ORM metadata. The real `backend/dev.db` is never touched, and the same tests run on SQLite
  or Postgres.
- EasyOCR, edge-tts, Groq, DistilGPT-2 and LanguageTool are faked by default, so the suite
  needs no API keys and no model downloads. spaCy, the phonetic checker and the classifier
  run for real.
- `m3_inflight` marks tests that use the tables M3's Postgres migration is re-keying.
  They pass on today's schema, and CI runs them as non-blocking until Phase 1 lands.

## CI (`.github/workflows/ci.yml`)

Runs on every push to every branch:

| Job | Blocking? |
|-----|-----------|
| Backend tests (SQLite): stable suite | ✅ |
| Backend tests (SQLite): `m3_inflight` suite | ⏳ non-blocking until Phase 1 |
| Backend tests (Postgres 16 service container) + `alembic upgrade head` once migrations exist | ⏳ non-blocking until Phase 1 |
| Frontend `npm run build` | ✅ |
| Frontend `npm run lint` | ⚠️ non-blocking: 3 pre-existing errors in `WritingPage.jsx` (M2) |
| Docker image build + `/health` boot check | ✅ on `main` / manual only (~3 GB image) |
| Real-model tests | manual (`workflow_dispatch` → *run_model_tests*) |

**When M3's migration merges:** delete the two `continue-on-error` lines marked
`PHASE 1` in `ci.yml` and drop the `-m "not m3_inflight"` filter.

## Deployment

### Backend → Railway

1. New project → *Deploy from GitHub repo* → this repo, branch `main`. Railway reads
   `railway.toml`, which builds the `Dockerfile`:
   - CPU-only torch (the default wheel bundles about 3 GB of CUDA)
   - `poppler-utils` for the scanned-PDF fallback, plus a JRE for LanguageTool
   - `HF_HUB_DISABLE_XET=1`, with `hf-xet` uninstalled
   - EasyOCR, DistilGPT-2, NLTK data, spaCy and LanguageTool downloaded **at build time**
     by `scripts/prewarm_models.py`, so the first request never downloads anything
2. Add the **Postgres** addon (once M3's migration is on `main`). `DATABASE_URL` is
   injected automatically, and `preDeployCommand` runs `alembic upgrade head` on every
   deploy. Without `DATABASE_URL` or `alembic.ini` it logs and skips.
3. Set the variables below, deploy, and check that `https://<app>.up.railway.app/health`
   returns `{"status":"ok"}`.
4. Use a plan with **≥ 4 GB RAM**: torch, EasyOCR, DistilGPT-2 and the LanguageTool JVM
   all sit in one process (`--workers 1` on purpose).

`nixpacks.toml` is a fallback builder kept in sync with the Dockerfile. Railway uses it
only if `railway.toml` is switched to `builder = "NIXPACKS"`.

### Frontend → Vercel

1. Import the repo and leave **Root Directory = repository root**. `vercel.json` runs the
   build in `frontend/`, serves `frontend/dist`, adds SPA rewrites, and skips rebuilds for
   backend-only commits.
2. Set `VITE_API_URL` to the Railway URL, then deploy.
3. Copy the resulting Vercel URL into Railway's `CORS_ORIGINS` and redeploy the backend.

### Environment variables

M4 *sets* these in the Railway/Vercel dashboards. They never go in the repo; `.env` is
gitignored and has never been committed.

| Variable | Where | Notes |
|----------|-------|-------|
| `VITE_API_URL` | Vercel | Railway backend URL, no trailing slash. Baked in at build time. |
| `CORS_ORIGINS` | Railway | Comma-separated. Set **after** the first Vercel deploy (needs its URL). `localhost:5173` is always allowed. |
| `SECRET_KEY` | Railway | JWT signing key. M2 already generated it, so reuse it and don't regenerate (that would log everyone out). The backend refuses to start without it. |
| `GROQ_API_KEY` | Railway | Used by simplification (F42–F44, `simplification_service.py`). The M4 guide says `ANTHROPIC_API_KEY`, but the code reads `GROQ_API_KEY`. |
| `GROQ_MODEL` | Railway | Optional. Defaults to `openai/gpt-oss-120b`. |
| `HF_HUB_DISABLE_XET` | Railway | `1`. Already baked into the Dockerfile; set it too if you build with nixpacks. |
| `DATABASE_URL` | Railway | Injected automatically by the Postgres addon. Not needed while on SQLite. |

> **If SQLite stays after all:** `backend/dev.db` lives inside the container and is wiped
> on every deploy or restart. A Railway Volume can't easily fix that, because the path is
> hardcoded next to the code in `models_temp.py`. Postgres is the production path.

### Deploy checklist

- [ ] CI is green on `main` (including the Postgres job once Phase 1 lands)
- [ ] Railway: variables set, Postgres addon attached, pre-deploy log shows `alembic upgrade head`
      (Postgres only)
- [ ] Railway build log shows `[prewarm] easyocr: ok`, `distilgpt2: ok`, `languagetool: ok`
- [ ] `/health` is OK, and the first `/nlp/check` takes about 10–15 s (LanguageTool JVM cold
      start, done once). The first `/ocr/image` should not trigger a download.
- [ ] Vercel: `VITE_API_URL` set, deployed. Then Railway `CORS_ORIGINS` = Vercel URL, redeployed.
- [ ] **Smoke test** (Actions → *Smoke test (deployed)*, or locally):
      `python tests/smoke/smoke_test.py --api <railway-url> --origin <vercel-url>`
      covers register → login → upload image → simplify → TTS → prediction (3 words plus the
      phrase pill) → drill a word → badge → analytics populated → second-account isolation
- [ ] In the browser: word-sync drift < 150 ms on a 20-word sentence
- [ ] Writing page: the phrase pill appears while typing and hides on accept/escape
- [ ] After populating `word_bank`: drill-due badge on the nav and alert card on the Homepage
- [ ] Upgrade Railway to a paid tier before demo week (no cold starts)

### Known, disclosed issues (not bugs to rediscover)

- **Reading-session logging fires only on the Stop click** (`handleStop()`), not on the
  audio `ended` event. Playback that finishes without a Stop click is never logged. This
  is pre-existing M1 behaviour that M3 flagged. The regression flow logs on Stop, as the
  UI does.
- **Classifier:** 63.6% overall accuracy against AC-26's 80% target. The Hard-recall
  target is met (86.5% ≥ 85%), and CI gates on that.
- **LanguageTool isn't preloaded at app startup.** The jar is baked into the image, but
  the JVM still starts on the first `/nlp/check`. Calling `get_tool()` in `main.py`'s
  lifespan would fix it (M2's file, flagged).
- **`pdf2image`** is imported by the scanned-PDF fallback but missing from
  `requirements.txt`. The Dockerfile installs it for now (flagged to M1).
