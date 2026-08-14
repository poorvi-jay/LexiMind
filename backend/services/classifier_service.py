"""
LexiMind M3 — Word Difficulty Classifier Service
Loads the trained RandomForest model once at import time and exposes
classify_word() / classify_words() for use by the /classify router (Phase 3).
"""
from pathlib import Path
import joblib
from nltk.tokenize import SyllableTokenizer
import wordfreq

_MODEL_PATH = Path(__file__).parent.parent / "ml" / "classifier.joblib"
_HARD_THRESHOLD = 0.40
_GUARD_MAX_LENGTH = 2  # words this short/common were never in CompLex's
                        # training data (only abbreviations were), so the
                        # model has no real signal here and defaults to
                        # Hard incorrectly. Verified: every length<=2 word
                        # tested was wrong; every length>=3 word was
                        # already correct. Disclosed deviation from frozen
                        # Phase 2 spec — bypasses model, forces Easy.

# Load once at module import — never reload per-request.
_model = joblib.load(_MODEL_PATH)
_syllable_tokenizer = SyllableTokenizer()


def extract_features(word: str) -> list:
    """Compute [syllables, frequency, length] for a single word.
    Must exactly match the feature extraction used in train_classifier.py."""
    try:
        syllables = len(_syllable_tokenizer.tokenize(word))
    except Exception:
        syllables = 1
    frequency = wordfreq.word_frequency(word, "en")
    length = len(word)
    return [syllables, frequency, length]


def _predict_batch(words: list) -> list:
    """Run one batched prediction for a list of words. Internal helper.
    Batching is required for performance — see Phase 2 Step 8 diagnosis:
    calling predict_proba() once per word is ~150-200x slower than
    calling it once on the full batch.

    Words of length <= _GUARD_MAX_LENGTH bypass the model entirely and
    are forced to Easy (see _GUARD_MAX_LENGTH docstring above)."""
    guarded = [w for w in words if len(w) <= _GUARD_MAX_LENGTH]
    needs_model = [w for w in words if len(w) > _GUARD_MAX_LENGTH]

    results_by_word = {
        w: {"word": w, "label": "Easy", "confidence": 1.0} for w in guarded
    }

    if needs_model:
        features = [extract_features(w) for w in needs_model]
        classes = _model.classes_
        hard_idx = list(classes).index("Hard")
        probs_batch = _model.predict_proba(features)

        for word, probs in zip(needs_model, probs_batch):
            if probs[hard_idx] >= _HARD_THRESHOLD:
                label = "Hard"
            else:
                remaining = {c: probs[i] for i, c in enumerate(classes) if c != "Hard"}
                label = max(remaining, key=remaining.get)
            confidence = float(max(probs))
            results_by_word[word] = {"word": word, "label": label, "confidence": round(confidence, 3)}

    return [results_by_word[w] for w in words]


def classify_word(word: str) -> dict:
    """Classify a single word. Returns {word, label, confidence}.
    Never raises — falls back to a safe default on any failure,
    per the 'classifier failures cannot crash Reading' requirement."""
    try:
        if not word or not word.strip():
            return {"word": word, "label": "Medium", "confidence": 0.0}
        return _predict_batch([word])[0]
    except Exception:
        return {"word": word, "label": "Medium", "confidence": 0.0}


def classify_words(words: list) -> list:
    """Classify a batch of words in ONE model call, deduplicating repeats
    for efficiency, and preserving the original order/duplicates in the
    returned list."""
    if not words:
        return []
    try:
        unique_words = list(dict.fromkeys(w for w in words if w and w.strip()))
        if not unique_words:
            return [{"word": w, "label": "Medium", "confidence": 0.0} for w in words]

        batch_results = _predict_batch(unique_words)
        results_by_word = {r["word"]: r for r in batch_results}

        return [
            results_by_word[w] if (w and w.strip() and w in results_by_word)
            else {"word": w, "label": "Medium", "confidence": 0.0}
            for w in words
        ]
    except Exception:
        return [{"word": w, "label": "Medium", "confidence": 0.0} for w in words]