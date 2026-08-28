"""W1.10: the runtime two-stage annotation flow.

LR labels every row; rows below `CONFIDENCE_THRESHOLD` escalate to Haiku.
Both paths write to `annotations` with the `annotator` field recording which
one produced the row — that column is the whole lineage story (§6), and it is
what makes the escalation rate and the cost saving measurable after the fact.

Threshold rationale is decision-log Entry #9 (W1.9).
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from creativesignal.annotate.bootstrap import build_prompt, parse_response
from creativesignal.annotate.classical import predict_with_confidence
from creativesignal.llm import HAIKU_MODEL, complete
from creativesignal.schema import Annotation

DB_PATH = Path("data/corpus.sqlite")

# W1.9 decision — see decision-log Entry #9. Deliberately a module constant
# and not a tunable parameter: it is a product decision with a cost
# consequence, so changing it should be a reviewable diff.
CONFIDENCE_THRESHOLD = 0.70

ANNOTATOR_LOGREG = "logreg"
ANNOTATOR_LLM = HAIKU_MODEL


@dataclass
class EscalationStats:
    total: int
    escalated: int
    kept: int

    @property
    def escalation_rate(self) -> float:
        return self.escalated / self.total if self.total else 0.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def annotate_row(
    models: dict,
    creative_id: str,
    headline: str | None,
    body_copy: str | None,
) -> tuple[Annotation, bool]:
    """Annotate one creative. Returns (annotation, escalated).

    Escalation is per-row, not per-axis: if *either* axis is low-confidence
    the row goes to the LLM, which relabels both. Splitting them would mean
    two LLM calls for one row and an annotation whose two halves came from
    different annotators — unattributable in the `annotator` column.
    """
    hook = predict_with_confidence(models["hook_type"], headline, body_copy)
    tone = predict_with_confidence(models["tone"], headline, body_copy)
    lowest = min(hook.confidence, tone.confidence)

    if lowest >= CONFIDENCE_THRESHOLD:
        return (
            Annotation(
                annotation_id=str(uuid.uuid4()),
                creative_id=creative_id,
                hook_type=hook.label,
                tone=tone.label,
                confidence=lowest,
                annotator=ANNOTATOR_LOGREG,
                annotated_at=_now(),
            ),
            False,
        )

    response = complete(
        build_prompt(headline or "", body_copy or ""),
        task="escalation",
        model=HAIKU_MODEL,
        prompt_version="bootstrap_label_v1",
        max_tokens=200,
    )
    llm_hook, llm_tone, _, _ = parse_response(response.text)
    return (
        Annotation(
            annotation_id=str(uuid.uuid4()),
            creative_id=creative_id,
            hook_type=llm_hook,
            tone=llm_tone,
            # The LLM does not emit a calibrated probability. Recording the
            # LR's confidence would misattribute it, so this stays null —
            # "no confidence score" is the honest value, not a made-up 1.0.
            confidence=None,
            annotator=ANNOTATOR_LLM,
            annotated_at=_now(),
        ),
        True,
    )


def write_annotations(annotations: list[Annotation], db_path: Path = DB_PATH) -> int:
    if not annotations:
        return 0
    rows = [
        (
            a.annotation_id, a.creative_id, a.hook_type, a.tone, a.confidence,
            a.annotator, a.annotated_at.isoformat() if a.annotated_at else None,
        )
        for a in annotations
    ]
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO annotations (annotation_id, creative_id, "
            "hook_type, tone, confidence, annotator, annotated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    return len(rows)


def annotate_corpus(db_path: Path = DB_PATH) -> EscalationStats:
    from creativesignal.annotate.classical import load

    models = load()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        creatives = conn.execute(
            "SELECT creative_id, headline, body_copy FROM creatives "
            "WHERE body_copy IS NOT NULL"
        ).fetchall()

    annotations, escalated = [], 0
    for row in creatives:
        annotation, did_escalate = annotate_row(
            models, row["creative_id"], row["headline"], row["body_copy"]
        )
        annotations.append(annotation)
        escalated += did_escalate
    write_annotations(annotations, db_path)
    return EscalationStats(len(creatives), escalated, len(creatives) - escalated)


def escalation_stats_from_db(db_path: Path = DB_PATH) -> EscalationStats:
    """Recover the escalation rate from what was actually written."""
    with sqlite3.connect(db_path) as conn:
        counts = dict(
            conn.execute("SELECT annotator, COUNT(*) FROM annotations GROUP BY annotator")
        )
    kept = counts.get(ANNOTATOR_LOGREG, 0)
    escalated = sum(n for a, n in counts.items() if a != ANNOTATOR_LOGREG)
    return EscalationStats(kept + escalated, escalated, kept)


def main() -> None:
    stats = annotate_corpus()
    print(
        f"annotated {stats.total} creatives — "
        f"{stats.kept} kept by LR, {stats.escalated} escalated to {HAIKU_MODEL}"
    )
    print(f"escalation rate: {stats.escalation_rate:.1%} (threshold {CONFIDENCE_THRESHOLD})")


if __name__ == "__main__":
    main()
