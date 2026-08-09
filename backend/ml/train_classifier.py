"""
LexiMind M3 — Word Difficulty Classifier Training Script
Ground truth: CompLex 2.0 (CC-BY 4.0), word-level aggregated complexity scores.
Features: [syllables, frequency, length]
Algorithm: RandomForestClassifier, Hard-probability threshold = 0.40
"""
import pandas as pd
import numpy as np
import json
import joblib
import sklearn
from datetime import datetime
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (classification_report, confusion_matrix,
                              accuracy_score, f1_score, recall_score)
from nltk.tokenize import SyllableTokenizer
import wordfreq

DATA_DIR = Path(__file__).parent / "data" / "complex"
OUTPUT_MODEL = Path(__file__).parent / "classifier.joblib"
OUTPUT_METADATA = Path(__file__).parent / "metadata.json"
HARD_THRESHOLD = 0.40
RANDOM_STATE = 42

def load_complex_data():
    train = pd.read_csv(DATA_DIR / "lcp_single_train.tsv", sep="\t")
    trial = pd.read_csv(DATA_DIR / "lcp_single_trial.tsv", sep="\t")
    test = pd.read_csv(DATA_DIR / "lcp_single_test.tsv", sep="\t")
    return pd.concat([train, trial, test])

def aggregate_to_word_level(df):
    word_level = df.groupby("token")["complexity"].mean().reset_index()
    word_level.columns = ["word", "complexity"]
    word_level["word"] = word_level["word"].str.lower()
    word_level = word_level[word_level["word"].str.isalpha()]
    word_level = word_level.drop_duplicates(subset="word").reset_index(drop=True)
    return word_level

_syllable_tokenizer = SyllableTokenizer()

def extract_features(word: str) -> list:
    try:
        syllables = len(_syllable_tokenizer.tokenize(word))
    except Exception:
        syllables = 1
    frequency = wordfreq.word_frequency(word, "en")
    length = len(word)
    return [syllables, frequency, length]

def predict_with_threshold(clf, X, hard_threshold=HARD_THRESHOLD):
    classes = clf.classes_
    hard_idx = list(classes).index("Hard")
    probs = clf.predict_proba(X)
    predictions = []
    for p in probs:
        if p[hard_idx] >= hard_threshold:
            predictions.append("Hard")
        else:
            remaining = {c: p[i] for i, c in enumerate(classes) if c != "Hard"}
            predictions.append(max(remaining, key=remaining.get))
    return np.array(predictions), probs

def main():
    print("Loading CompLex dataset...")
    raw = load_complex_data()
    print(f"  Total word-in-context instances: {len(raw)}")

    word_level = aggregate_to_word_level(raw)
    print(f"  Unique words after aggregation: {len(word_level)}")

    print("Extracting features...")
    feats = word_level["word"].apply(extract_features)
    word_level["syl"] = feats.apply(lambda x: x[0])
    word_level["freq"] = feats.apply(lambda x: x[1])
    word_level["len"] = feats.apply(lambda x: x[2])

    words = word_level["word"].values
    idx_train, idx_test = train_test_split(
        np.arange(len(word_level)), test_size=0.2, random_state=RANDOM_STATE
    )

    train_complexity = word_level.iloc[idx_train]["complexity"]
    _, bin_edges = pd.qcut(train_complexity, q=3, retbins=True, duplicates="drop")
    bin_edges[0] = -np.inf
    bin_edges[-1] = np.inf
    word_level["label"] = pd.cut(
        word_level["complexity"], bins=bin_edges, labels=["Easy", "Medium", "Hard"]
    )

    # Save the clean training table for transparency/documentation
    export_cols = ["word", "syl", "freq", "len", "complexity", "label"]
    export_path = Path(__file__).parent / "data" / "training_data_clean.csv"
    word_level[export_cols].to_csv(export_path, index=False)
    print(f"  Saved clean training table to {export_path}")

    print(f"  Label distribution: {word_level['label'].value_counts().to_dict()}")

    X = word_level[["syl", "freq", "len"]].values
    y = word_level["label"].astype(str).values
    X_train, X_test = X[idx_train], X[idx_test]
    y_train, y_test = y[idx_train], y[idx_test]
    w_train, w_test = words[idx_train], words[idx_test]

    leakage = set(w_train) & set(w_test)
    assert len(leakage) == 0, f"Train/test word leakage detected: {leakage}"
    print(f"  Train: {len(X_train)}  Test: {len(X_test)}  Leakage check: PASSED")

    print("Training RandomForestClassifier...")
    clf = RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_leaf=10,
        random_state=RANDOM_STATE, n_jobs=-1
    )
    clf.fit(X_train, y_train)

    y_pred, _ = predict_with_threshold(clf, X_test)

    acc = accuracy_score(y_test, y_pred)
    macro_f1 = f1_score(y_test, y_pred, average="macro")
    hard_recall = recall_score(y_test, y_pred, labels=["Hard"], average="macro")

    print("\n" + classification_report(y_test, y_pred, digits=3))
    print("Confusion matrix (Easy, Hard, Medium):")
    print(confusion_matrix(y_test, y_pred, labels=["Easy", "Hard", "Medium"]))
    print(f"\nAccuracy: {acc*100:.2f}%")
    print(f"Macro-F1: {macro_f1*100:.2f}%")
    print(f"Hard-recall: {hard_recall*100:.2f}%")

    print(f"\nSaving model to {OUTPUT_MODEL}...")
    joblib.dump(clf, OUTPUT_MODEL)

    metadata = {
        "dataset": "CompLex 2.0 (CC-BY 4.0, MMU-TDMLab/CompLex)",
        "ground_truth": "word-level mean of contextual complexity scores",
        "feature_order": ["syllables", "frequency", "length"],
        "algorithm": "RandomForestClassifier",
        "hyperparameters": {
            "n_estimators": 200, "max_depth": 8,
            "min_samples_leaf": 10, "random_state": RANDOM_STATE
        },
        "hard_probability_threshold": HARD_THRESHOLD,
        "label_boundaries_complexity_scale": bin_edges.tolist(),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "accuracy": round(acc, 4),
        "macro_f1": round(macro_f1, 4),
        "hard_recall": round(hard_recall, 4),
        "sklearn_version": sklearn.__version__,
        "training_date": datetime.utcnow().isoformat(),
    }
    with open(OUTPUT_METADATA, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved metadata to {OUTPUT_METADATA}")

if __name__ == "__main__":
    main()