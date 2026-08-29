"""W1.8: confusion matrix, precision/recall table, escalation-rate stat.

The P/R table is what the W1.9 threshold decision is made against, so it
reports accuracy *at each candidate threshold* alongside the escalation rate
that threshold implies — the cost/accuracy tradeoff in one table.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from creativesignal.annotate.classical import predict_with_confidence

CONFUSION_PNG = Path("eval/results/confusion_{axis}.png")
CANDIDATE_THRESHOLDS = (0.0, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60, 0.70)


@dataclass
class ThresholdRow:
    """One row of the cost/accuracy tradeoff table."""

    threshold: float
    escalation_rate: float
    accuracy_on_kept: float
    n_kept: int
    n_escalated: int


def cross_val_predictions(rows: list, axis: str, folds: int = 5):
    """Out-of-fold predictions, so accuracy isn't measured on training data.

    Uses stratified CV and returns (y_true, y_pred, confidences). Folds are
    capped by the rarest class so stratification stays valid on a small seed.
    """
    import numpy as np
    from sklearn.model_selection import StratifiedKFold

    from creativesignal.annotate.classical import (
        _build_pipeline,
        _text_of,
        drop_unlearnable_classes,
    )
    from creativesignal.annotate.taxonomy import UNCLEAR_LABEL

    pairs = [
        (_text_of(r.headline, r.body_copy), getattr(r, axis))
        for r in rows
        if getattr(r, axis) != UNCLEAR_LABEL and _text_of(r.headline, r.body_copy)
    ]
    # Same class filter as training, so CV evaluates what was actually fit.
    t_list, l_list, _ = drop_unlearnable_classes(
        [t for t, _ in pairs], [l for _, l in pairs], axis
    )
    texts = np.array(t_list)
    labels = np.array(l_list)

    counts = {label: int((labels == label).sum()) for label in set(labels.tolist())}
    n_splits = max(2, min(folds, min(counts.values())))

    y_true, y_pred, confidences = [], [], []
    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=20260828)
    for train_idx, test_idx in splitter.split(texts, labels):
        pipeline = _build_pipeline()
        pipeline.fit(texts[train_idx], labels[train_idx])
        probabilities = pipeline.predict_proba(texts[test_idx])
        for true_label, row in zip(labels[test_idx], probabilities):
            best = int(row.argmax())
            y_true.append(str(true_label))
            y_pred.append(str(pipeline.classes_[best]))
            confidences.append(float(row[best]))
    return y_true, y_pred, confidences


def threshold_table(y_true, y_pred, confidences) -> list[ThresholdRow]:
    """Accuracy-on-kept vs. escalation rate, per candidate threshold (W1.9).

    "Accuracy on kept" is the number that matters: rows below the threshold
    go to the LLM, so the LR's error rate on the rows it *keeps* is what the
    two-stage system actually ships.
    """
    table: list[ThresholdRow] = []
    total = len(y_true)
    for threshold in CANDIDATE_THRESHOLDS:
        kept = [
            (t, p) for t, p, c in zip(y_true, y_pred, confidences) if c >= threshold
        ]
        n_kept = len(kept)
        correct = sum(1 for t, p in kept if t == p)
        table.append(
            ThresholdRow(
                threshold=threshold,
                escalation_rate=(total - n_kept) / total if total else 0.0,
                accuracy_on_kept=correct / n_kept if n_kept else 0.0,
                n_kept=n_kept,
                n_escalated=total - n_kept,
            )
        )
    return table


def precision_recall_table(y_true, y_pred) -> str:
    from sklearn.metrics import classification_report

    return classification_report(y_true, y_pred, zero_division=0)


def save_confusion_matrix(y_true, y_pred, axis: str, path: Path | None = None) -> Path:
    import matplotlib

    matplotlib.use("Agg")  # headless: this runs in CI and in `make annotate`
    import matplotlib.pyplot as plt
    from sklearn.metrics import ConfusionMatrixDisplay

    out = path or Path(str(CONFUSION_PNG).format(axis=axis))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 6))
    ConfusionMatrixDisplay.from_predictions(
        y_true, y_pred, ax=ax, xticks_rotation=45, colorbar=False, cmap="Greens"
    )
    ax.set_title(f"{axis}: out-of-fold confusion matrix")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def print_report(rows: list, models: dict) -> None:
    for axis in ("hook_type", "tone"):
        print(f"\n{'=' * 60}\n{axis}\n{'=' * 60}")
        y_true, y_pred, confidences = cross_val_predictions(rows, axis)
        print(precision_recall_table(y_true, y_pred))
        png = save_confusion_matrix(y_true, y_pred, axis)
        print(f"confusion matrix -> {png}\n")
        print(f"{'thresh':>7} {'escal%':>8} {'acc@kept':>9} {'kept':>6} {'escal':>6}")
        for row in threshold_table(y_true, y_pred, confidences):
            print(
                f"{row.threshold:>7.2f} {row.escalation_rate:>8.1%} "
                f"{row.accuracy_on_kept:>9.1%} {row.n_kept:>6} {row.n_escalated:>6}"
            )
