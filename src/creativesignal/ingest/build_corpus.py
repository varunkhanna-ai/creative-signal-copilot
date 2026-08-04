"""Builds the two-table SQLite layout (`creatives`, `annotations`) for the
corpus. Columns mirror `creativesignal.schema.Creative` / `Annotation`.

This only creates the schema — loading rows is W1.4+.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path("data/corpus.sqlite")

CREATE_CREATIVES = """
CREATE TABLE IF NOT EXISTS creatives (
    creative_id     TEXT PRIMARY KEY,
    source_type     TEXT NOT NULL CHECK (source_type IN ('tier1', 'tier2', 'tier3')),
    advertiser      TEXT NOT NULL,
    platform        TEXT NOT NULL,
    category        TEXT NOT NULL,
    headline        TEXT,
    body_copy       TEXT,
    source_url      TEXT,
    date_observed   TEXT NOT NULL,
    rights_note     TEXT NOT NULL,
    start_date      TEXT,
    days_active     INTEGER,
    variant_count   INTEGER,
    proxy_bucket    TEXT CHECK (proxy_bucket IN ('high', 'mid', 'low'))
);
"""

CREATE_ANNOTATIONS = """
CREATE TABLE IF NOT EXISTS annotations (
    annotation_id   TEXT PRIMARY KEY,
    creative_id     TEXT NOT NULL REFERENCES creatives(creative_id),
    hook_type       TEXT,
    tone            TEXT,
    confidence      REAL,
    annotator       TEXT NOT NULL,
    annotated_at    TEXT
);
"""


def build_corpus(db_path: Path = DB_PATH) -> None:
    """Create `creatives` and `annotations` in `db_path` if they don't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(CREATE_CREATIVES)
        conn.execute(CREATE_ANNOTATIONS)
        conn.commit()


if __name__ == "__main__":
    build_corpus()
