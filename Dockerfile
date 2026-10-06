# LexiMind backend (FastAPI) — Owner: M4
# Railway builds this (railway.toml: builder = "DOCKERFILE").
# Frontend is deployed separately on Vercel (vercel.json).
#
# DB engine: this image works for both outcomes of Phase 1.
#   - Postgres (M3 migration): DATABASE_URL is injected by Railway's
#     Postgres addon; migrations run via railway.toml preDeployCommand.
#   - SQLite: backend/dev.db lives inside the container and is WIPED on
#     every deploy/restart. Not acceptable for production — see README.

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Hugging Face Xet stalled / 404'd on distilgpt2 during local setup.
    HF_HUB_DISABLE_XET=1 \
    # Bake every model cache into the image (filled by prewarm below).
    HF_HOME=/opt/models/huggingface \
    EASYOCR_MODULE_PATH=/opt/models/easyocr \
    NLTK_DATA=/opt/models/nltk_data \
    LTP_PATH=/opt/models/languagetool

# poppler-utils: pdf2image's scanned-PDF fallback in ocr_service.py
# default-jre-headless: LanguageTool (grammar checks, /nlp/check)
# libglib2.0-0 / libgl1: OpenCV runtime libs used by EasyOCR
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      poppler-utils default-jre-headless libglib2.0-0 libgl1 curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only torch first (the default PyPI wheel bundles ~3 GB of CUDA).
# "2.12.1+cpu" satisfies requirements.txt's torch==2.12.1 pin.
RUN pip install --index-url https://download.pytorch.org/whl/cpu \
      torch==2.12.1 torchvision==0.27.1

COPY requirements.txt .
RUN pip install -r requirements.txt \
 # pdf2image: imported by ocr_service.py's scanned-PDF fallback but
 # missing from requirements.txt (flagged to M1).
 # psycopg2-binary: driver SQLAlchemy uses for Railway's postgresql:// URL.
 # alembic: `alembic upgrade head` on deploy once M3's migration lands.
 # (Both are no-ops until then; drop them here once requirements.txt has them.)
 && pip install pdf2image==1.17.0 psycopg2-binary==2.9.10 alembic==1.16.5 \
 # Uninstall hf-xet so huggingface_hub can't fall back to Xet at all.
 && pip uninstall -y hf-xet

# Pre-download EasyOCR, DistilGPT-2, NLTK data, spaCy, LanguageTool at
# build time instead of on the first request.
COPY scripts/prewarm_models.py scripts/prewarm_models.py
RUN python scripts/prewarm_models.py

# Whole repo minus .dockerignore (frontend, tests, .env, *.db excluded),
# so alembic.ini + migrations are picked up wherever M3 puts them.
COPY . .

# Non-root runtime user; model caches must stay readable/writable.
RUN useradd --create-home --uid 1000 app \
 && chown -R app:app /app /opt/models
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/health" || exit 1

# One worker: each worker would load its own copy of torch/EasyOCR/
# DistilGPT-2 and the LanguageTool JVM (~2-3 GB per process).
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
