"""W2.5: the hybrid retrieval pipeline (§8).

    parse filters -> semantic + keyword -> merge/rerank -> cited results
    + coverage statement

Implements decision-log Entry #10 exactly:
  1. metadata filters are a hard pre-filter, applied before scoring
  2. per-query min-max normalization, then a weighted sum
  3. dedupe to creative level, keeping max component score

Every result carries its creative ID and source link, and every response
carries a coverage statement — the honesty rule is structural here, not a
formatting step applied later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from creativesignal.schema import Creative, HONESTY_RULE, coverage_statement
from creativesignal.sources.base import SearchFilters
from creativesignal.sources.curated import DB_PATH, CuratedCorpusConnector

# Entry #10: equal weight is the honest default with no golden set to tune
# against. One named constant so W2.8 can sweep it when one exists.
SEMANTIC_WEIGHT = 0.5
KEYWORD_WEIGHT = 1.0 - SEMANTIC_WEIGHT

# Filter vocabulary the query parser understands.
_PLATFORM_TERMS = {"facebook": "facebook", "instagram": "instagram", "meta": "facebook",
                   "tiktok": "tiktok"}
_TIER_TERMS = {"tier 3": "tier3", "tier-3": "tier3", "tier3": "tier3",
               "tier 2": "tier2", "tier-2": "tier2", "tier2": "tier2"}
_BUCKET_TERMS = {"long-running": "high", "long running": "high",
                 "short-lived": "low", "short lived": "low"}


@dataclass
class RetrievedCreative:
    """One creative in the final ranking, with its full scoring provenance."""

    creative: Creative
    score: float
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    matched_representations: list[str] = field(default_factory=list)

    @property
    def creative_id(self) -> str:
        return self.creative.creative_id

    @property
    def citation(self) -> str:
        """How this result is cited in generated text."""
        url = self.creative.source_url
        return f"[{self.creative_id}]" + (f" {url}" if url else "")


@dataclass
class RetrievalResponse:
    """Results plus the honesty apparatus that must travel with them."""

    query: str
    results: list[RetrievedCreative]
    filters_applied: dict
    coverage_statement: str
    honesty_rule: str = HONESTY_RULE

    @property
    def creative_ids(self) -> list[str]:
        return [r.creative_id for r in self.results]


def parse_filters(query: str) -> SearchFilters:
    """Extract structured filters from natural-language query text.

    Deliberately a small keyword mapping, not an LLM call: filter parsing has
    to run with no API key, must be deterministic for eval reproducibility,
    and is the single easiest thing to explain in an interview. Unrecognized
    text simply stays part of the free-text query.
    """
    lowered = query.lower()
    platform = next((v for k, v in _PLATFORM_TERMS.items() if k in lowered), None)
    source_type = next((v for k, v in _TIER_TERMS.items() if k in lowered), None)
    proxy_bucket = next((v for k, v in _BUCKET_TERMS.items() if k in lowered), None)
    return SearchFilters(
        platform=platform, source_type=source_type, proxy_bucket=proxy_bucket
    )


def normalize(scores: dict[str, float]) -> dict[str, float]:
    """Min-max to [0,1] within one query's results (Entry #10, rule 2).

    All-equal scores map to 1.0, not 0.0: if every candidate matched equally
    well, they are all good matches, and mapping them to zero would let the
    other retriever silently decide the entire ranking.
    """
    if not scores:
        return {}
    values = list(scores.values())
    low, high = min(values), max(values)
    if high - low < 1e-9:
        return {k: 1.0 for k in scores}
    return {k: (v - low) / (high - low) for k, v in scores.items()}


def hybrid_search(
    query: str,
    limit: int = 5,
    filters: SearchFilters | None = None,
    db_path: Path = DB_PATH,
    chroma_dir: Path | None = None,
    semantic_weight: float = SEMANTIC_WEIGHT,
) -> RetrievalResponse:
    """Run both retrievers, fuse, and return cited results with coverage."""
    from creativesignal.retrieval.index import CHROMA_DIR, semantic_search

    chroma_dir = chroma_dir or CHROMA_DIR
    filters = filters or parse_filters(query)
    source = CuratedCorpusConnector(db_path)

    # 1. Hard pre-filter: the candidate set both retrievers may draw from.
    allowed = {c.creative_id: c for c in source.all_creatives(filters)}
    if not allowed:
        return RetrievalResponse(query, [], filters.as_dict(), coverage_statement(0))

    # 2a. Keyword. Over-fetch so fusion has candidates beyond the top few.
    keyword_raw: dict[str, float] = {}
    for result in source.search(query, filters=filters, limit=limit * 3):
        keyword_raw[result.creative_id] = result.score

    # 2b. Semantic, deduped to creative level keeping the best representation.
    semantic_raw: dict[str, float] = {}
    representations: dict[str, list[str]] = {}
    try:
        hits = semantic_search(query, limit=limit, filters=filters.as_dict(),
                               chroma_dir=chroma_dir)
    except Exception:
        hits = []  # no index built yet — degrade to keyword-only, don't crash
    for hit in hits:
        if hit.creative_id not in allowed:
            continue  # index may be staler than the DB filter
        if hit.score > semantic_raw.get(hit.creative_id, -1.0):
            semantic_raw[hit.creative_id] = hit.score
        representations.setdefault(hit.creative_id, []).append(hit.representation)

    # 3. Normalize per-query, then weighted sum over the union.
    semantic = normalize(semantic_raw)
    keyword = normalize(keyword_raw)
    fused: list[RetrievedCreative] = []
    for creative_id in set(semantic) | set(keyword):
        s, k = semantic.get(creative_id, 0.0), keyword.get(creative_id, 0.0)
        matched = list(dict.fromkeys(representations.get(creative_id, [])))
        if creative_id in keyword:
            matched.append("bm25")
        fused.append(
            RetrievedCreative(
                creative=allowed[creative_id],
                score=semantic_weight * s + (1.0 - semantic_weight) * k,
                semantic_score=s,
                keyword_score=k,
                matched_representations=matched,
            )
        )

    # Tie-break by id so equal scores rank deterministically — eval reruns
    # must not shuffle.
    fused.sort(key=lambda r: (-r.score, r.creative_id))
    top = fused[:limit]
    return RetrievalResponse(
        query=query,
        results=top,
        filters_applied=filters.as_dict(),
        coverage_statement=coverage_statement(len(top)),
    )


def semantic_only_search(
    query: str, limit: int = 5, filters: SearchFilters | None = None,
    db_path: Path = DB_PATH, chroma_dir: Path | None = None,
) -> RetrievalResponse:
    """The W2.8 comparison baseline: semantic weight pinned to 1.0."""
    return hybrid_search(
        query, limit, filters, db_path, chroma_dir, semantic_weight=1.0
    )


def keyword_only_search(
    query: str, limit: int = 5, filters: SearchFilters | None = None,
    db_path: Path = DB_PATH, chroma_dir: Path | None = None,
) -> RetrievalResponse:
    """The W1.11 naive baseline, expressed in the same response type."""
    return hybrid_search(
        query, limit, filters, db_path, chroma_dir, semantic_weight=0.0
    )
