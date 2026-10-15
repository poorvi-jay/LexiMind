"""
scripts/prewarm_models.py — Owner: M4
Download every model/data file the backend lazy-loads, at BUILD time,
so the first user request on Railway never pays for (or stalls on) a
download. Used by the Dockerfile and nixpacks.toml; safe to run locally.

Cache locations come from env vars set in the Dockerfile so they land
inside the image:
  NLTK_DATA, EASYOCR_MODULE_PATH, HF_HOME, LTP_PATH

HF_HUB_DISABLE_XET=1 (+ hf-xet uninstalled) avoids the Xet download
stall that returned 404s for distilgpt2 during local setup.

Exits non-zero on any failure: a broken build beats a deploy that
hangs on the first OCR / prediction / grammar request.

  python scripts/prewarm_models.py            # everything
  python scripts/prewarm_models.py --skip languagetool
"""
import argparse
import os
import sys
import time

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")


def nltk_data():
    import nltk

    target = os.environ.get("NLTK_DATA")
    for pkg in ("cmudict", "wordnet", "omw-1.4"):
        if not nltk.download(pkg, quiet=True, download_dir=target, raise_on_error=True):
            raise RuntimeError(f"nltk download failed: {pkg}")


def spacy_model():
    import spacy

    spacy.load("en_core_web_sm")


def easyocr_models():
    import easyocr

    easyocr.Reader(["en"], gpu=False)


def distilgpt2():
    from transformers import pipeline

    gen = pipeline("text-generation", model="distilgpt2")
    gen("Hello", max_new_tokens=1, pad_token_id=50256)


def languagetool():
    import language_tool_python

    tool = language_tool_python.LanguageTool("en-US")
    try:
        tool.check("This are a test.")
    finally:
        tool.close()


STEPS = {
    "nltk": nltk_data,
    "spacy": spacy_model,
    "easyocr": easyocr_models,
    "distilgpt2": distilgpt2,
    "languagetool": languagetool,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip", nargs="*", default=[], choices=list(STEPS))
    args = parser.parse_args()

    failed = []
    for name, fn in STEPS.items():
        if name in args.skip:
            print(f"[prewarm] {name}: skipped")
            continue
        start = time.time()
        try:
            fn()
            print(f"[prewarm] {name}: ok ({time.time() - start:.1f}s)")
        except Exception as exc:  # report every failure, then fail the build
            print(f"[prewarm] {name}: FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            failed.append(name)
    if failed:
        sys.exit(f"[prewarm] failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
