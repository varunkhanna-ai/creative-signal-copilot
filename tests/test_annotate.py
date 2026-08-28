"""W1.8/W1.10 tests: training guards, confidence, escalation routing.

The escalation tests stub the LLM call — the routing decision is the logic
worth testing, and it must be testable without an API key.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import pytest

from creativesignal.annotate import escalate
from creativesignal.annotate.classical import (
    InsufficientTrainingData,
    Prediction,
    predict_with_confidence,
    train_axis,
)
from creativesignal.annotate.escalate import (
    ANNOTATOR_LOGREG,
    CONFIDENCE_THRESHOLD,
    EscalationStats,
    annotate_row,
    escalation_stats_from_db,
    write_annotations,
)
from creativesignal.ingest.build_corpus import build_corpus


@dataclass
class Row:
    headline: str
    body_copy: str
    hook_type: str
    tone: str


def _seed(n_per_class: int = 12) -> list[Row]:
    """A synthetic seed set with two clearly separable classes per axis."""
    rows: list[Row] = []
    for i in range(n_per_class):
        rows.append(
            Row(
                headline=f"Dermatologist tested formula {i}",
                body_copy="Clinically proven, lab verified, dermatologist recommended.",
                hook_type="authority_expert",
                tone="clinical",
            )
        )
        rows.append(
            Row(
                headline=f"Save 40 percent today {i}",
                body_copy="Limited time discount, bundle offer, free shipping now.",
                hook_type="offer_led",
                tone="urgent",
            )
        )
    return rows


# --- training guards -------------------------------------------------------


def test_refuses_to_train_on_too_few_rows():
    """B2: refusing beats reporting an accuracy figure that means nothing."""
    with pytest.raises(InsufficientTrainingData, match="need >="):
        train_axis(_seed(n_per_class=2), "hook_type")


def test_refuses_to_train_on_a_single_class():
    rows = [
        Row(f"h{i}", "clinically proven derm tested", "authority_expert", "clinical")
        for i in range(30)
    ]
    with pytest.raises(InsufficientTrainingData, match="only one class"):
        train_axis(rows, "hook_type")


def test_unclear_rows_are_excluded_from_training():
    """`unclear` is an escape hatch, never a predictable class."""
    rows = _seed() + [Row("x", "garbled", "unclear", "unclear") for _ in range(4)]
    model = train_axis(rows, "hook_type")
    assert "unclear" not in set(model.classes_)


# --- prediction ------------------------------------------------------------


def test_predicts_a_frozen_label_with_confidence():
    model = train_axis(_seed(), "hook_type")
    prediction = predict_with_confidence(
        model, "Save 40 percent", "Limited time discount and free shipping."
    )
    assert prediction.label == "offer_led"
    assert 0.0 <= prediction.confidence <= 1.0


def test_empty_text_is_unclear_at_zero_confidence():
    model = train_axis(_seed(), "hook_type")
    prediction = predict_with_confidence(model, None, None)
    assert prediction == Prediction("unclear", 0.0)


# --- escalation routing ----------------------------------------------------


class _StubModel:
    """Minimal stand-in exposing the two attributes the predictor touches.

    Returns numpy arrays because that is what a fitted sklearn pipeline
    returns — a list here would pass tests the real model would fail.
    """

    def __init__(self, label: str, confidence: float, n_other: int = 5):
        import numpy as np

        # Spread the remaining mass over several classes so `confidence` is
        # genuinely the argmax — with only one other class, a "low
        # confidence" of 0.2 would make the *other* class the prediction.
        self.classes_ = np.array([label, *(f"other_{i}" for i in range(n_other))])
        rest = (1.0 - confidence) / n_other
        self._probabilities = np.array([[confidence, *([rest] * n_other)]])
        assert self._probabilities.argmax() == 0, "stub must predict `label`"

    def predict_proba(self, _texts):
        return self._probabilities


def _models(confidence: float):
    return {
        "hook_type": _StubModel("offer_led", confidence),
        "tone": _StubModel("urgent", confidence),
    }


def test_high_confidence_row_is_kept_by_logreg(monkeypatch):
    def _fail(*args, **kwargs):
        raise AssertionError("must not call the LLM above threshold")

    monkeypatch.setattr(escalate, "complete", _fail)
    annotation, escalated = annotate_row(_models(0.95), "c1", "Save 40%", "Discount.")
    assert escalated is False
    assert annotation.annotator == ANNOTATOR_LOGREG
    assert annotation.hook_type == "offer_led"
    assert annotation.confidence == pytest.approx(0.95)


def test_low_confidence_row_escalates_to_the_llm(monkeypatch):
    calls = []

    class _Response:
        text = '{"hook_type": "social_proof", "tone": "warm_reassuring"}'

    def _fake_complete(prompt, **kwargs):
        calls.append(kwargs.get("task"))
        return _Response()

    monkeypatch.setattr(escalate, "complete", _fake_complete)
    annotation, escalated = annotate_row(_models(0.30), "c2", "Hmm", "Ambiguous copy.")
    assert escalated is True
    assert calls == ["escalation"]
    assert annotation.annotator == escalate.ANNOTATOR_LLM
    assert annotation.hook_type == "social_proof"


def test_escalated_annotation_has_no_confidence_score(monkeypatch):
    """The LLM emits no calibrated probability — null, not a fabricated 1.0."""

    class _Response:
        text = '{"hook_type": "social_proof", "tone": "playful"}'

    monkeypatch.setattr(escalate, "complete", lambda *a, **k: _Response())
    annotation, _ = annotate_row(_models(0.30), "c3", "Hmm", "Ambiguous.")
    assert annotation.confidence is None


def test_either_axis_below_threshold_escalates_the_whole_row(monkeypatch):
    """Per-row escalation: one annotator per annotation, always attributable."""

    class _Response:
        text = '{"hook_type": "offer_led", "tone": "urgent"}'

    monkeypatch.setattr(escalate, "complete", lambda *a, **k: _Response())
    models = {
        "hook_type": _StubModel("offer_led", 0.99),
        "tone": _StubModel("urgent", 0.30),  # only tone is unsure
    }
    _, escalated = annotate_row(models, "c4", "Save 40%", "Discount.")
    assert escalated is True


def test_threshold_boundary_is_inclusive(monkeypatch):
    def _fail(*args, **kwargs):
        raise AssertionError("exactly at threshold must not escalate")

    monkeypatch.setattr(escalate, "complete", _fail)
    _, escalated = annotate_row(
        _models(CONFIDENCE_THRESHOLD), "c5", "Save 40%", "Discount."
    )
    assert escalated is False


# --- persistence -----------------------------------------------------------


def test_annotations_persist_with_annotator_attribution(tmp_path, monkeypatch):
    db = tmp_path / "corpus.sqlite"
    build_corpus(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO creatives (creative_id, source_type, advertiser, platform, "
            "category, date_observed, rights_note) VALUES "
            "('c1', 'tier2', 'x', 'y', 'skincare', '2026-01-01', 'note')"
        )

    class _Response:
        text = '{"hook_type": "social_proof", "tone": "playful"}'

    monkeypatch.setattr(escalate, "complete", lambda *a, **k: _Response())
    kept, _ = annotate_row(_models(0.99), "c1", "h", "b")
    write_annotations([kept], db)

    stats = escalation_stats_from_db(db)
    assert stats == EscalationStats(total=1, escalated=0, kept=1)
    assert stats.escalation_rate == 0.0


def test_escalation_rate_is_computed_from_what_was_written(tmp_path):
    db = tmp_path / "corpus.sqlite"
    build_corpus(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO creatives (creative_id, source_type, advertiser, platform, "
            "category, date_observed, rights_note) VALUES "
            "('c1', 'tier2', 'x', 'y', 'skincare', '2026-01-01', 'n')"
        )
        conn.executemany(
            "INSERT INTO annotations (annotation_id, creative_id, annotator) VALUES (?, 'c1', ?)",
            [("a1", ANNOTATOR_LOGREG), ("a2", ANNOTATOR_LOGREG), ("a3", escalate.ANNOTATOR_LLM)],
        )
    stats = escalation_stats_from_db(db)
    assert (stats.total, stats.escalated) == (3, 1)
    assert stats.escalation_rate == pytest.approx(1 / 3)
