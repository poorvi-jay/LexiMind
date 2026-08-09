"""
LexiMind M3 — Classifier unit tests
Run with: python -m pytest backend/ml/test_classifier.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.classifier_service import extract_features, classify_word, classify_words


def test_extract_features_shape():
    feats = extract_features("cat")
    assert len(feats) == 3
    assert isinstance(feats[0], int)   # syllables
    assert isinstance(feats[1], float) # frequency
    assert isinstance(feats[2], int)   # length


def test_extract_features_known_word():
    syl, freq, length = extract_features("cat")
    assert syl == 1
    assert length == 3
    assert freq > 0


def test_extract_features_oov_word():
    # must not crash on nonsense/unknown input
    feats = extract_features("xyzzyplonk")
    assert len(feats) == 3


def test_extract_features_empty_string():
    # must not crash
    feats = extract_features("")
    assert len(feats) == 3


def test_classify_word_returns_correct_shape():
    result = classify_word("cat")
    assert set(result.keys()) == {"word", "label", "confidence"}
    assert result["label"] in ("Easy", "Medium", "Hard")
    assert 0.0 <= result["confidence"] <= 1.0


def test_classify_word_empty_string_safe():
    result = classify_word("")
    assert result["label"] == "Medium"
    assert result["confidence"] == 0.0


def test_classify_words_empty_list():
    assert classify_words([]) == []


def test_classify_words_batch():
    results = classify_words(["cat", "encyclopedia", "semiconductor"])
    assert len(results) == 3
    assert all(r["label"] in ("Easy", "Medium", "Hard") for r in results)


def test_classify_words_deduplication_consistency():
    # same word repeated should get identical results every time
    results = classify_words(["cat", "cat", "cat"])
    assert results[0] == results[1] == results[2]


def test_classify_word_never_raises():
    weird_inputs = ["123", "a", "æøå", "COVID19", "supercalifragilisticexpialidocious"]
    for w in weird_inputs:
        result = classify_word(w)  # should not raise
        assert "label" in result