"""W4.6b: persist every brief->concepts generation to the `runs` table.

The third table, kept separate from `creatives` and `annotations` (§6): these
are *generated outputs*, not source records and not derived labels. Nothing
here is ever written back into `creatives`.

Two consumers beyond the page's "past runs" list:
  - **W6.1b demo mode** replays a stored run with zero API calls, so the
    deployed app is instant and costs nothing.
  - **W5.8 human eval** draws its fixed output set from stable run IDs, so
    every scorer rates identical outputs and results stay re-traceable.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from creativesignal.schema import Concept, ReviewResult, Run, TrendReport
from creativesignal.sources.curated import DB_PATH

CREATE_RUNS = """
CREATE TABLE IF NOT EXISTS runs (
    run_id                  TEXT PRIMARY KEY,
    created_at              TEXT NOT NULL,
    brief                   TEXT NOT NULL,
    retrieved_creative_ids  TEXT NOT NULL,
    trend_report            TEXT,
    concepts                TEXT NOT NULL,
    review_results          TEXT NOT NULL,
    model_versions          TEXT NOT NULL,
    prompt_versions         TEXT NOT NULL,
    token_cost_usd          REAL NOT NULL DEFAULT 0.0
);
"""


def ensure_runs_table(db_path: Path = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(CREATE_RUNS)
        conn.commit()


def new_run_id() -> str:
    return f"run_{uuid.uuid4().hex[:12]}"


def save_run(run: Run, db_path: Path = DB_PATH) -> str:
    """Write-through. Returns the run_id."""
    ensure_runs_table(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO runs (run_id, created_at, brief, "
            "retrieved_creative_ids, trend_report, concepts, review_results, "
            "model_versions, prompt_versions, token_cost_usd) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run.run_id,
                run.created_at.isoformat(),
                json.dumps(run.brief),
                json.dumps(run.retrieved_creative_ids),
                run.trend_report.model_dump_json() if run.trend_report else None,
                json.dumps([c.model_dump(mode="json") for c in run.concepts]),
                json.dumps([r.model_dump(mode="json") for r in run.review_results]),
                json.dumps(run.model_versions),
                json.dumps(run.prompt_versions),
                run.token_cost_usd,
            ),
        )
        conn.commit()
    return run.run_id


def _row_to_run(row: sqlite3.Row) -> Run:
    return Run(
        run_id=row["run_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        brief=json.loads(row["brief"]),
        retrieved_creative_ids=json.loads(row["retrieved_creative_ids"]),
        trend_report=(
            TrendReport.model_validate_json(row["trend_report"])
            if row["trend_report"]
            else None
        ),
        concepts=[Concept.model_validate(c) for c in json.loads(row["concepts"])],
        review_results=[
            ReviewResult.model_validate(r) for r in json.loads(row["review_results"])
        ],
        model_versions=json.loads(row["model_versions"]),
        prompt_versions=json.loads(row["prompt_versions"]),
        token_cost_usd=row["token_cost_usd"],
    )


def load_run(run_id: str, db_path: Path = DB_PATH) -> Run | None:
    ensure_runs_table(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return _row_to_run(row) if row else None


def list_runs(limit: int = 25, db_path: Path = DB_PATH) -> list[Run]:
    """Most recent first — what the page's "past runs" list shows."""
    ensure_runs_table(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_run(row) for row in rows]


def build_run(
    brief: dict,
    retrieved_creative_ids: list[str],
    trend_report: TrendReport | None,
    concepts: list[Concept],
    review_results: list[ReviewResult],
    token_cost_usd: float = 0.0,
) -> Run:
    """Assemble a Run, stamping the model and prompt versions in use.

    Versions are recorded per run so a later eval can tell which prompt
    produced which output — the L3 prompt-A/B measurement depends on it.
    """
    from creativesignal.llm import HAIKU_MODEL, SONNET_MODEL

    return Run(
        run_id=new_run_id(),
        created_at=datetime.now(timezone.utc),
        brief=brief,
        retrieved_creative_ids=retrieved_creative_ids,
        trend_report=trend_report,
        concepts=concepts,
        review_results=review_results,
        model_versions={"synthesis": SONNET_MODEL, "annotation": HAIKU_MODEL},
        prompt_versions={"concepts": "concept_v1", "summary": "analyst_summary_v1"},
        token_cost_usd=token_cost_usd,
    )


def attach_image(
    run_id: str, concept_title: str, image_path: str, db_path: Path = DB_PATH
) -> bool:
    """Record a generated image against one concept in a persisted run.

    Image generation is opt-in and happens *after* a run is saved (Entry #33),
    so this updates the stored run in place rather than rewriting it. Returns
    False if the run or the concept is not found, so a caller can report the
    mismatch instead of silently doing nothing.

    Only `image_path` changes — the concept's text is left exactly as it was
    generated and reviewed, so attaching an image can never alter the content
    the reviewer already passed judgment on.
    """
    run = load_run(run_id, db_path)
    if run is None:
        return False

    matched = False
    for concept in run.concepts:
        if concept.title == concept_title:
            concept.image_path = image_path
            matched = True
            break
    if not matched:
        return False

    save_run(run, db_path)
    return True
