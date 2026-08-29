"""W5.2: `creative-intelligence-mcp` — four read-only tools over the corpus.

Same corpus, two clients: the Streamlit app and any MCP-capable coding agent.
Contracts are decision-log Entry #18.

**Read-only, enforced not just intended** (AGENTS.md): this module imports no
write function, and `readonly_connection()` opens SQLite with `mode=ro` so a
write fails at the driver level. A test asserts that.

Runs with **no API key** — every tool is retrieval and arithmetic.

    make mcp
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from creativesignal.schema import HONESTY_RULE, coverage_statement  # noqa: E402
from creativesignal.sources.curated import DB_PATH  # noqa: E402

mcp = FastMCP("creative-intelligence-mcp")

CORPUS_CAVEAT = (
    "Corpus is a curated public sample for a portfolio project. Tier-2 rows "
    "are synthetic ad copy with no provenance; Tier-3 rows carry real "
    "ad-library provenance. Counts describe this corpus only."
)


def readonly_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Open the corpus read-only. A write raises at the driver."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _envelope(payload: dict) -> str:
    """Attach the honesty framing to every payload leaving the server.

    This is the one surface where output travels outside our UI, so the
    framing must ride in the payload — there is no footer out here.
    """
    return json.dumps({**payload, "honesty_rule": HONESTY_RULE}, indent=2)


@mcp.tool()
def search_creatives(
    query: str,
    limit: int = 5,
    source_type: str | None = None,
    platform: str | None = None,
) -> str:
    """Search the curated skincare ad corpus. Returns cited creative records.

    Every hit carries its creative_id and, where one exists, a source link.
    """
    from creativesignal.agents.tools import search_creatives as _search

    result = _search(
        query, limit=limit, source_type=source_type, platform=platform
    )
    return _envelope(
        {
            "query": query,
            "hits": [hit.model_dump() for hit in result.hits],
            "filters_applied": result.filters_applied,
            "coverage_statement": result.coverage_statement,
        }
    )


@mcp.tool()
def get_creative_details(creative_id: str) -> str:
    """Full record for one creative: source fields, annotations, analyst summary.

    Annotations carry an `annotator` field recording whether a classifier or
    an LLM produced the label.
    """
    from creativesignal.agents.tools import get_creative_details as _details

    details = _details(creative_id)
    if not details.found:
        return _envelope(
            {"creative_id": creative_id, "found": False,
             "message": "No creative with that id in this corpus."}
        )
    return _envelope(details.model_dump())


@mcp.tool()
def get_category_stats(category: str | None = None) -> str:
    """Corpus composition: counts by tier, platform, hook_type, tone.

    Use this to orient before searching — it shows what the corpus actually
    contains, including how much of it carries provenance.
    """
    with readonly_connection() as conn:
        where, params = ("WHERE category = ?", [category]) if category else ("", [])
        total = conn.execute(
            f"SELECT COUNT(*) FROM creatives {where}", params
        ).fetchone()[0]
        by_tier = dict(
            conn.execute(
                f"SELECT source_type, COUNT(*) FROM creatives {where} GROUP BY source_type",
                params,
            )
        )
        by_platform = dict(
            conn.execute(
                f"SELECT platform, COUNT(*) FROM creatives {where} GROUP BY platform",
                params,
            )
        )
        with_source = conn.execute(
            f"SELECT COUNT(*) FROM creatives {where} "
            f"{'AND' if where else 'WHERE'} source_url IS NOT NULL",
            params,
        ).fetchone()[0]
        by_hook = dict(
            conn.execute(
                "SELECT hook_type, COUNT(*) FROM annotations "
                "WHERE hook_type IS NOT NULL GROUP BY hook_type"
            )
        )
        by_tone = dict(
            conn.execute(
                "SELECT tone, COUNT(*) FROM annotations "
                "WHERE tone IS NOT NULL GROUP BY tone"
            )
        )

    return _envelope(
        {
            "category": category or "all",
            "total_creatives": total,
            "by_tier": by_tier,
            "by_platform": by_platform,
            "with_source_link": with_source,
            "provenance_coverage": (
                f"{with_source}/{total}" if total else "0/0"
            ),
            "hook_type_distribution": by_hook,
            "tone_distribution": by_tone,
            "caveat": CORPUS_CAVEAT,
        }
    )


@mcp.tool()
def generate_evidence_report(query: str, limit: int = 8) -> str:
    """Assemble a cited evidence report for a query. Makes no LLM call.

    Returns the retrieved creatives plus prevalence counts over hook_type and
    tone. Prevalence describes what is present in the retrieved set — it is
    not evidence that any pattern performs better.
    """
    from creativesignal.agents.tools import analyze_pattern
    from creativesignal.agents.tools import search_creatives as _search

    found = _search(query, limit=limit)
    ids = [hit.creative_id for hit in found.hits]

    patterns = []
    for dimension in ("hook_type", "tone"):
        analysis = analyze_pattern(ids, dimension)
        patterns.extend(
            {
                "pattern": p.description,
                "prevalence": p.prevalence_statement,
                "cited_creative_ids": p.cited_creative_ids,
            }
            for p in analysis.patterns
        )

    return _envelope(
        {
            "query": query,
            "retrieved_creative_ids": ids,
            "evidence": [
                {
                    "creative_id": hit.creative_id,
                    "headline": hit.headline,
                    "body_copy": hit.body_copy,
                    "source_url": hit.source_url,
                }
                for hit in found.hits
            ],
            "patterns": patterns,
            "patterns_note": (
                "Prevalence within the retrieved set. Descriptive, not causal, "
                "and not a performance claim."
            )
            if patterns
            else "No annotations available, so no prevalence patterns computed.",
            "coverage_statement": coverage_statement(len(ids)),
            "caveat": CORPUS_CAVEAT,
        }
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
