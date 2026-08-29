"""Builds the two-table SQLite layout (`creatives`, `annotations`) for the
corpus. Columns mirror `creativesignal.schema.Creative` / `Annotation`.

W1.4 adds the load path: Tier-1/2/3 loaders -> normalized `creatives` rows.
Nothing derived or generated is ever written into `creatives` (§6 lineage).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from creativesignal.schema import Creative

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


CREATIVE_COLUMNS: tuple[str, ...] = (
    "creative_id", "source_type", "advertiser", "platform", "category",
    "headline", "body_copy", "source_url", "date_observed", "rights_note",
    "start_date", "days_active", "variant_count", "proxy_bucket",
)


def build_corpus(db_path: Path = DB_PATH) -> None:
    """Create `creatives` and `annotations` in `db_path` if they don't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(CREATE_CREATIVES)
        conn.execute(CREATE_ANNOTATIONS)
        conn.commit()


def _to_row(creative: Creative) -> tuple:
    """Flatten a Creative to a positional row; dates go in as ISO strings."""
    data = creative.model_dump()
    return tuple(
        value.isoformat() if hasattr(value, "isoformat") else value
        for value in (data[col] for col in CREATIVE_COLUMNS)
    )


def insert_creatives(creatives: list[Creative], db_path: Path = DB_PATH) -> int:
    """Upsert creatives by `creative_id`. Returns the number of rows written.

    Idempotent so `make ingest` can be re-run: re-ingesting the same source
    replaces the row rather than erroring or duplicating it.
    """
    if not creatives:
        return 0
    placeholders = ", ".join("?" * len(CREATIVE_COLUMNS))
    sql = (
        f"INSERT OR REPLACE INTO creatives ({', '.join(CREATIVE_COLUMNS)}) "
        f"VALUES ({placeholders})"
    )
    with sqlite3.connect(db_path) as conn:
        conn.executemany(sql, [_to_row(c) for c in creatives])
        conn.commit()
    return len(creatives)


def count_by_tier(db_path: Path = DB_PATH) -> dict[str, int]:
    with sqlite3.connect(db_path) as conn:
        return dict(
            conn.execute("SELECT source_type, COUNT(*) FROM creatives GROUP BY source_type")
        )


def main(db_path: Path = DB_PATH) -> None:
    from creativesignal.ingest.load_tier1 import load_tier1
    from creativesignal.ingest.load_tier2 import load_tier2
    from creativesignal.ingest.load_tier3 import load_tier3

    build_corpus(db_path)
    total = 0
    for name, loader in (
        ("tier1", load_tier1),
        ("tier2", load_tier2),
        ("tier3", load_tier3),
    ):
        records = loader()
        written = insert_creatives(records, db_path)
        total += written
        print(f"  {name}: {written} rows")
    print(f"\ncreatives table: {total} rows total -> {db_path}")
    print(f"  by tier: {count_by_tier(db_path)}")


if __name__ == "__main__":
    main()
