"""W1.8: TF-IDF + logistic regression over the corrected seed set.

This is the cheap first pass in the Job A two-stage flow: LR labels
everything, and only rows it is unsure about escalate to the LLM (W1.10).
The cost story depends on that split being real, so `predict_with_confidence`
returns a calibrated-ish probability, not just a label.

One model per axis (`hook_type`, `tone`) — they are independent labels
(Entry #8), so a single multi-output model would only couple them.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from creativesignal.annotate.taxonomy import UNCLEAR_LABEL

MODEL_PATH = Path("data/annotator.pkl")
Axis = Literal["hook_type", "tone"]

# Small corpus, short texts: unigrams+bigrams, no aggressive pruning.
TFIDF_KWARGS = dict(ngram_range=(1, 2), min_df=1, sublinear_tf=True, strip_accents="unicode")
# `saga` + balanced classes: the seed set is small and label-imbalanced.
LOGREG_KWARGS = dict(max_iter=2000, class_weight="balanced", random_state=20260828)

MIN_ROWS_PER_CLASS = 2
MIN_TRAINING_ROWS = 20


class InsufficientTrainingData(RuntimeError):
    """Raised when the seed set is too small to train an honest classifier.

    Better to refuse than to fit a model on a handful of rows and report an
    accuracy figure that means nothing (decision-log B2).
    """


@dataclass
class Prediction:
    label: str
    confidence: float

    @property
    def is_confident(self) -> bool:
        from creativesignal.annotate.escalate import CONFIDENCE_THRESHOLD

        return self.confidence >= CONFIDENCE_THRESHOLD


def _text_of(headline: str | None, body_copy: str | None) -> str:
    """Headline and body concatenated — the hook lives in the opening."""
    return f"{headline or ''}\n{body_copy or ''}".strip()


def _build_pipeline():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(**TFIDF_KWARGS)),
            ("clf", LogisticRegression(**LOGREG_KWARGS)),
        ]
    )


def _check_trainable(texts: list[str], labels: list[str], axis: str) -> None:
    from collections import Counter

    if len(texts) < MIN_TRAINING_ROWS:
        raise InsufficientTrainingData(
            f"{axis}: {len(texts)} training rows, need >= {MIN_TRAINING_ROWS}. "
            "The corpus is too small to train an honest classifier — see "
            "docs/decision-log.md B2."
        )
    counts = Counter(labels)
    if len(counts) < 2:
        raise InsufficientTrainingData(
            f"{axis}: only one class present ({list(counts)}). Nothing to learn."
        )
    thin = {label: n for label, n in counts.items() if n < MIN_ROWS_PER_CLASS}
    if thin:
        raise InsufficientTrainingData(
            f"{axis}: class(es) with fewer than {MIN_ROWS_PER_CLASS} examples: "
            f"{thin}. Stratified evaluation is impossible."
        )


def train_axis(rows: list, axis: Axis):
    """Fit one axis. `rows` are SeedLabel-like objects with the axis attribute.

    Rows labeled `unclear` are excluded: `unclear` is an escape hatch, not a
    class to predict (Entry #8). Training on it would teach the model to
    produce it.
    """
    pairs = [
        (_text_of(r.headline, r.body_copy), getattr(r, axis))
        for r in rows
        if getattr(r, axis) != UNCLEAR_LABEL
    ]
    pairs = [(text, label) for text, label in pairs if text]
    if not pairs:
        raise InsufficientTrainingData(f"{axis}: no usable rows after filtering.")
    texts, labels = map(list, zip(*pairs))
    _check_trainable(texts, labels, axis)
    pipeline = _build_pipeline()
    pipeline.fit(texts, labels)
    return pipeline


def train(rows: list) -> dict[str, object]:
    """Fit both axes. Returns {axis: fitted pipeline}."""
    return {axis: train_axis(rows, axis) for axis in ("hook_type", "tone")}


def predict_with_confidence(model, headline: str | None, body_copy: str | None) -> Prediction:
    """Predict one axis with the model's own probability as confidence.

    Confidence is `max(predict_proba)` — the probability mass on the winning
    class. It is the quantity the escalation threshold (W1.9) is set against,
    so it must come from the model rather than a heuristic.
    """
    text = _text_of(headline, body_copy)
    if not text:
        return Prediction(UNCLEAR_LABEL, 0.0)
    probabilities = model.predict_proba([text])[0]
    best = int(probabilities.argmax())
    return Prediction(str(model.classes_[best]), float(probabilities[best]))


def save(models: dict[str, object], path: Path = MODEL_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        pickle.dump(models, handle)


def load(path: Path = MODEL_PATH) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing — train first: `python -m creativesignal.annotate.classical`"
        )
    with path.open("rb") as handle:
        return pickle.load(handle)


def main() -> None:
    from creativesignal.annotate.bootstrap import load_corrected_seed
    from creativesignal.annotate.report import print_report

    rows = load_corrected_seed()
    print(f"Training on {len(rows)} corrected seed rows ...")
    try:
        models = train(rows)
    except InsufficientTrainingData as exc:
        print(f"\n  REFUSED TO TRAIN: {exc}")
        return
    save(models)
    print(f"  saved -> {MODEL_PATH}\n")
    print_report(rows, models)


if __name__ == "__main__":
    main()
