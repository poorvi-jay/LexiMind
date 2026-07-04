import re
from transformers import pipeline

predictor = pipeline("text-generation", model="distilgpt2")


def predict_words(prefix: str) -> list[str]:
    """
    Generate up to 3 single-word next-word suggestions for the
    given prefix.

    Note: DistilGPT-2 generates subword tokens, so occasionally a
    suggestion will be a word fragment (e.g. "irc", "ers") rather
    than a complete word. This is a known limitation of small
    models doing single-token generation, discussed with the team
    and accepted as-is rather than over-filtering (see commit log).

    Returns an empty list if prefix is empty/whitespace-only.
    """
    if not prefix or not prefix.strip():
        return []

    results = predictor(
        prefix,
        max_new_tokens=1,
        num_return_sequences=3,
        do_sample=True,
        temperature=0.7,
        pad_token_id=50256,
    )

    words = []
    for r in results:
        generated = r["generated_text"][len(prefix):]
        matches = re.findall(r"\b[a-zA-Z]+\b", generated)
        if matches and matches[0] not in words:
            words.append(matches[0])

    return words[:3]


def predict_phrase(prefix: str) -> str:
    """
    Generate a short (up to 5 new tokens, capped at 40 chars)
    phrase continuation for the given prefix.

    Per PRD rule: NEVER raises/returns an error for an empty or
    unusable result — returns "" so the frontend can hide the
    4th suggestion pill (AC-22).
    """
    if not prefix or not prefix.strip():
        return ""

    results = predictor(
        prefix,
        max_new_tokens=5,
        num_return_sequences=1,
        do_sample=True,
        temperature=0.7,
        pad_token_id=50256,
    )

    generated = results[0]["generated_text"][len(prefix):]
    phrase = generated.strip().split(".")[0]
    phrase = re.sub(r"[^a-zA-Z\s']", "", phrase).strip()

    if not re.search(r"[a-zA-Z]", phrase):
        return ""

    return phrase[:40]