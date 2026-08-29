"""W2.2/W2.3: the two retrieval representations (§8). No chunking, ever.

The retrieval unit is a whole structured creative record, expressed two ways:

  1. **Creative card** — deterministic assembly of schema fields. Free, always
     available, no API key. Matches literal vocabulary (ingredients, product
     names, offer language).
  2. **Analyst summary** — an LLM characterization of what the ad *does*.
     Matches strategist vocabulary ("authority-led," "ingredient-forward")
     that appears nowhere in the ad's own copy.

Both are embedded and both point at the same `creative_id`. The pair is the
product's core design claim: a query in strategist language can find an ad
whose copy shares no words with it.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from creativesignal.llm import HAIKU_MODEL, complete, load_prompt
from creativesignal.schema import Creative, CreativeCard

DB_PATH = Path("data/corpus.sqlite")
SUMMARY_PROMPT = "analyst_summary_v1"

CREATE_SUMMARIES = """
CREATE TABLE IF NOT EXISTS analyst_summaries (
    creative_id     TEXT PRIMARY KEY REFERENCES creatives(creative_id),
    summary         TEXT NOT NULL,
    model           TEXT NOT NULL,
    prompt_version  TEXT NOT NULL
);
"""


def build_card_text(creative: Creative) -> str:
    """Assemble the creative card — deterministic, no model involved.

    Field labels are included so the embedding sees structure; a bare
    concatenation would let an advertiser name and a headline blur together.
    Empty fields are omitted rather than rendered as "None", which would
    otherwise become a high-frequency token across the index.
    """
    rows = [
        ("Advertiser", creative.advertiser),
        ("Platform", creative.platform),
        ("Category", creative.category),
        ("Headline", creative.headline),
        ("Body", creative.body_copy),
    ]
    lines = [f"{label}: {value}" for label, value in rows if value]
    if creative.proxy_bucket:
        # Named as a proxy in the text itself, so even the index carries the
        # descriptive framing rather than implying a performance tier.
        lines.append(f"Longevity proxy bucket (not performance): {creative.proxy_bucket}")
    return "\n".join(lines)


def generate_analyst_summary(creative: Creative) -> str:
    """One Haiku-tier call. High volume, cheap — §0.1's tier split."""
    prompt = load_prompt(SUMMARY_PROMPT).format(
        advertiser=creative.advertiser,
        headline=creative.headline or "(none)",
        body_copy=creative.body_copy or "(none)",
    )
    response = complete(
        prompt,
        task="analyst_summary",
        model=HAIKU_MODEL,
        prompt_version=SUMMARY_PROMPT,
        max_tokens=300,
    )
    return response.text.strip()


def ensure_summary_table(db_path: Path = DB_PATH) -> None:
    """Summaries are derived, so they get their own table — never `creatives`."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(CREATE_SUMMARIES)
        conn.commit()


def load_summaries(db_path: Path = DB_PATH) -> dict[str, str]:
    ensure_summary_table(db_path)
    with sqlite3.connect(db_path) as conn:
        return dict(conn.execute("SELECT creative_id, summary FROM analyst_summaries"))


def save_summary(
    creative_id: str, summary: str, db_path: Path = DB_PATH,
    model: str = HAIKU_MODEL, prompt_version: str = SUMMARY_PROMPT,
) -> None:
    ensure_summary_table(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO analyst_summaries "
            "(creative_id, summary, model, prompt_version) VALUES (?, ?, ?, ?)",
            (creative_id, summary, model, prompt_version),
        )
        conn.commit()


def build_card(
    creative: Creative,
    summary: str | None = None,
    annotation: dict | None = None,
) -> CreativeCard:
    """Assemble the full retrieval unit for one creative."""
    annotation = annotation or {}
    return CreativeCard(
        creative_id=creative.creative_id,
        card_text=build_card_text(creative),
        analyst_summary=summary,
        advertiser=creative.advertiser,
        platform=creative.platform,
        source_url=creative.source_url,
        date_observed=creative.date_observed,
        hook_type=annotation.get("hook_type"),
        tone=annotation.get("tone"),
        proxy_bucket=creative.proxy_bucket,
    )


def load_annotations(db_path: Path = DB_PATH) -> dict[str, dict]:
    """Latest annotation per creative, for card metadata."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT creative_id, hook_type, tone FROM annotations "
            "ORDER BY annotated_at"
        ).fetchall()
    return {row["creative_id"]: dict(row) for row in rows}


def build_all_cards(db_path: Path = DB_PATH) -> list[CreativeCard]:
    """Every creative as a card, with summaries and annotations if present.

    Missing summaries are not an error: the card representation alone is a
    working index, so retrieval degrades rather than fails when W2.3 has not
    been run or no API key is available.
    """
    from creativesignal.sources.curated import CuratedCorpusConnector

    creatives = CuratedCorpusConnector(db_path).all_creatives()
    summaries = load_summaries(db_path)
    annotations = load_annotations(db_path)
    return [
        build_card(c, summaries.get(c.creative_id), annotations.get(c.creative_id))
        for c in creatives
    ]


def main(db_path: Path = DB_PATH) -> None:
    """W2.3: batch-generate analyst summaries for the corpus."""
    from creativesignal.llm import has_api_key
    from creativesignal.sources.curated import CuratedCorpusConnector

    creatives = CuratedCorpusConnector(db_path).all_creatives()
    existing = load_summaries(db_path)
    pending = [c for c in creatives if c.creative_id not in existing]

    print(f"{len(creatives)} creatives, {len(existing)} already summarized.")
    if not pending:
        print("Nothing to do.")
        return
    if not has_api_key():
        print(
            f"{len(pending)} need summaries but ANTHROPIC_API_KEY is not set. "
            "Cards alone still index and retrieve — see docs/decision-log.md B3."
        )
        return

    for i, creative in enumerate(pending, start=1):
        save_summary(creative.creative_id, generate_analyst_summary(creative), db_path)
        print(f"  [{i}/{len(pending)}] {creative.creative_id}")
    print(f"\nwrote {len(pending)} analyst summaries.")


if __name__ == "__main__":
    main()
