"""W3.2: the five §9 agent tools as plain, Pydantic-typed functions.

No agent framework — these are ordinary functions wrapping existing modules
(AGENTS.md). Names are fixed by §9 and must not be renamed:

    search_creatives, get_creative_details, analyze_pattern,
    generate_concepts, run_evaluation

The MCP server (W5.2) wraps this same layer, so the app and an external
coding agent hit identical code over one corpus.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from creativesignal.schema import Concept, Pattern, coverage_statement
from creativesignal.sources.base import SearchFilters
from creativesignal.sources.curated import DB_PATH, CuratedCorpusConnector

# Prompt lineage: v1 was the original; v2 added `visual_direction` (Entry
# #34); v3 constrains it to product-only framing (Entry #38). Each is a new
# file rather than an edit, because prompts are versioned (AGENTS.md) and
# every persisted run stamps the version that produced it — editing one in
# place would make old runs claim provenance they do not have.
CONCEPT_PROMPT = "concept_v3"


# --- typed I/O ------------------------------------------------------------


class CreativeHit(BaseModel):
    """One retrieved creative, flattened for tool output."""

    creative_id: str
    headline: Optional[str] = None
    body_copy: Optional[str] = None
    advertiser: str
    platform: str
    source_url: Optional[str] = None
    score: float = 0.0
    matched_via: list[str] = Field(default_factory=list)


class SearchCreativesResult(BaseModel):
    query: str
    hits: list[CreativeHit] = Field(default_factory=list)
    filters_applied: dict = Field(default_factory=dict)
    coverage_statement: str = ""


class CreativeDetails(BaseModel):
    creative_id: str
    found: bool
    creative: Optional[dict] = None
    annotations: list[dict] = Field(default_factory=list)
    analyst_summary: Optional[str] = None


class PatternAnalysis(BaseModel):
    """Prevalence counts over a set of creatives. Descriptive only."""

    dimension: str
    total_examined: int
    patterns: list[Pattern] = Field(default_factory=list)
    coverage_statement: str = ""
    note: str = (
        "Counts describe what is present in the retrieved set. They are not "
        "evidence that any pattern performs better than another."
    )


# --- the five tools -------------------------------------------------------


def search_creatives(
    query: str,
    limit: int = 5,
    source_type: str | None = None,
    platform: str | None = None,
    proxy_bucket: str | None = None,
    db_path: Path = DB_PATH,
) -> SearchCreativesResult:
    """Hybrid search over the corpus. Every hit carries its ID and source link."""
    from creativesignal.retrieval.hybrid import hybrid_search

    explicit = SearchFilters(
        source_type=source_type, platform=platform, proxy_bucket=proxy_bucket
    )
    # An explicitly-passed filter wins over one parsed from the query text.
    filters = explicit if explicit.as_dict() else None
    response = hybrid_search(query, limit=limit, filters=filters, db_path=db_path)
    return SearchCreativesResult(
        query=query,
        hits=[
            CreativeHit(
                creative_id=r.creative_id,
                headline=r.creative.headline,
                body_copy=r.creative.body_copy,
                advertiser=r.creative.advertiser,
                platform=r.creative.platform,
                source_url=r.creative.source_url,
                score=r.score,
                matched_via=r.matched_representations,
            )
            for r in response.results
        ],
        filters_applied=response.filters_applied,
        coverage_statement=response.coverage_statement,
    )


def get_creative_details(
    creative_id: str, db_path: Path = DB_PATH
) -> CreativeDetails:
    """Full record for one creative: source fields, annotations, summary."""
    import sqlite3

    from creativesignal.retrieval.cards import load_summaries

    creative = CuratedCorpusConnector(db_path).get(creative_id)
    if creative is None:
        return CreativeDetails(creative_id=creative_id, found=False)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        annotations = [
            dict(row)
            for row in conn.execute(
                "SELECT hook_type, tone, confidence, annotator FROM annotations "
                "WHERE creative_id = ?",
                (creative_id,),
            )
        ]
    return CreativeDetails(
        creative_id=creative_id,
        found=True,
        creative=creative.model_dump(mode="json"),
        annotations=annotations,
        analyst_summary=load_summaries(db_path).get(creative_id),
    )


def analyze_pattern(
    creative_ids: list[str],
    dimension: str = "hook_type",
    db_path: Path = DB_PATH,
) -> PatternAnalysis:
    """Count how often each value of `dimension` appears across creatives.

    This is the only place prevalence numbers are produced, so the
    descriptive framing is attached here rather than left to the prompt: a
    caller cannot get a count from this tool without also getting the note
    that a count is not a performance claim.
    """
    import sqlite3

    if dimension in {"hook_type", "tone"}:
        with sqlite3.connect(db_path) as conn:
            placeholders = ",".join("?" * len(creative_ids)) or "NULL"
            rows = conn.execute(
                f"SELECT creative_id, {dimension} FROM annotations "
                f"WHERE creative_id IN ({placeholders}) AND {dimension} IS NOT NULL",
                creative_ids,
            ).fetchall()
    else:
        source = CuratedCorpusConnector(db_path)
        rows = [
            (cid, getattr(source.get(cid), dimension, None))
            for cid in creative_ids
            if source.get(cid) is not None
        ]
        rows = [(cid, value) for cid, value in rows if value is not None]

    counts: Counter[str] = Counter(value for _, value in rows)
    ids_by_value: dict[str, list[str]] = {}
    for creative_id, value in rows:
        ids_by_value.setdefault(str(value), []).append(creative_id)

    total = len(creative_ids)
    patterns = [
        Pattern(
            description=f"{dimension} = {value}",
            prevalence_count=count,
            total_examined=total,
            cited_creative_ids=ids_by_value.get(str(value), []),
        )
        for value, count in counts.most_common()
    ]
    return PatternAnalysis(
        dimension=dimension,
        total_examined=total,
        patterns=patterns,
        coverage_statement=coverage_statement(total),
    )


def generate_concepts(
    brief: str,
    evidence_ids: list[str],
    n_concepts: int = 3,
    db_path: Path = DB_PATH,
) -> list[Concept]:
    """Generate concepts grounded in specific retrieved creatives.

    Concepts citing an ID outside `evidence_ids` are dropped: a citation the
    agent invented is the exact failure the honesty rule forbids.
    """
    from creativesignal.llm import SONNET_MODEL, complete, load_prompt
    from creativesignal.slice import format_evidence, parse_concepts
    from creativesignal.sources.base import SearchResult

    source = CuratedCorpusConnector(db_path)
    creatives = [c for c in (source.get(cid) for cid in evidence_ids) if c]
    if not creatives:
        return []

    evidence = format_evidence(
        [SearchResult(creative=c, score=0.0, retrieved_by="agent") for c in creatives]
    )
    prompt = load_prompt(CONCEPT_PROMPT).format(
        brief=brief,
        n_examples=len(creatives),
        evidence=evidence,
        n_concepts=n_concepts,
    )
    response = complete(
        prompt,
        task="generate_concepts",
        model=SONNET_MODEL,
        prompt_version=CONCEPT_PROMPT,
        max_tokens=2500,
    )
    parsed = parse_concepts(response.text)
    if not parsed:
        # A parse failure here is otherwise silent: the caller sees an empty
        # list indistinguishable from "the model legitimately produced
        # nothing." Log the raw text so a real occurrence is diagnosable
        # instead of leaving a "0 concepts" run with nothing to inspect
        # after the fact. See decision-log Entry #29.
        import logging

        logging.getLogger(__name__).warning(
            "generate_concepts: parse_concepts returned 0 concepts from a "
            "non-empty LLM response. Raw response follows.\n%s",
            response.text,
        )
    allowed = {c.creative_id for c in creatives}
    return [
        concept
        for concept in parsed
        if set(concept.cited_creative_ids) <= allowed
    ]


def run_evaluation(k: int = 5) -> dict:
    """Run the retrieval eval. Returns summaries, or why it could not run."""
    from creativesignal.eval.metrics import load_golden_set
    from creativesignal.eval.run_eval import _conditions, run_condition

    try:
        golden = load_golden_set()
    except FileNotFoundError as exc:
        return {"ran": False, "reason": str(exc)}
    if not golden:
        return {
            "ran": False,
            "reason": (
                "Golden set is empty — W2.6 (Human) is outstanding. See "
                "docs/decision-log.md B2."
            ),
        }
    summaries = [run_condition(n, fn, golden, k) for n, fn in _conditions().items()]
    return {
        "ran": True,
        "n_queries": len(golden),
        "summaries": [s.as_row() for s in summaries],
    }


TOOLS = {
    "search_creatives": search_creatives,
    "get_creative_details": get_creative_details,
    "analyze_pattern": analyze_pattern,
    "generate_concepts": generate_concepts,
    "run_evaluation": run_evaluation,
}
