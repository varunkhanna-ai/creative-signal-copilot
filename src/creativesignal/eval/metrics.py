"""W2.8/W4.8: hand-rolled retrieval metrics. Every formula explainable.

Deliberately not a framework: Recall@5 and Precision@5 are a few lines each,
and being able to state exactly what the denominator is — in an interview or
in the README — is worth more here than a dependency.

Counting rule is decision-log Entry #11: **metrics are computed over creative
IDs, deduplicated.** A creative that matched on both its card and its analyst
summary counts once. The golden set labels creatives, not representations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

GOLDEN_SET = Path("src/creativesignal/eval/golden_set.jsonl")


@dataclass
class GoldenQuery:
    """One labeled query: the text, and the creative IDs a human called relevant."""

    query: str
    relevant_creative_ids: list[str]
    notes: str = ""

    @property
    def relevant(self) -> set[str]:
        return set(self.relevant_creative_ids)


@dataclass
class QueryScore:
    query: str
    recall_at_k: float
    precision_at_k: float
    n_relevant: int
    n_retrieved: int
    n_hit: int
    missed_ids: list[str] = field(default_factory=list)


@dataclass
class EvalSummary:
    """Aggregate over a golden set, with the sample size always attached."""

    condition: str
    k: int
    n_queries: int
    mean_recall_at_k: float
    mean_precision_at_k: float
    per_query: list[QueryScore] = field(default_factory=list)

    def as_row(self) -> dict:
        return {
            "condition": self.condition,
            "k": self.k,
            "n_queries": self.n_queries,
            "recall@k": round(self.mean_recall_at_k, 4),
            "precision@k": round(self.mean_precision_at_k, 4),
        }


def recall_at_k(relevant: set[str], retrieved: list[str], k: int = 5) -> float:
    """|relevant ∩ top-k| / |relevant|.

    Undefined with no relevant documents; returns 0.0 so a mislabeled golden
    query can't silently inflate the mean.
    """
    if not relevant:
        return 0.0
    top_k = set(retrieved[:k])
    return len(relevant & top_k) / len(relevant)


def precision_at_k(relevant: set[str], retrieved: list[str], k: int = 5) -> float:
    """|relevant ∩ top-k| / |actually returned|.

    The denominator is the number of results actually returned, not a literal
    k. On a small corpus a query can return fewer than k; dividing by k would
    penalize the retriever for the corpus's size rather than its own ranking
    (Entry #11).
    """
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    return len(relevant & set(top_k)) / len(top_k)


def citation_correctness(cited_ids: list[str], retrieved_ids: list[str]) -> float:
    """W4.8: the fraction of cited IDs that were actually retrieved.

    This is the hallucinated-citation metric. A generated concept citing an
    ID that never appeared in its evidence is the specific failure the
    honesty rule forbids — "traceable to examples" is false if the example
    was invented. 1.0 means every citation is real; no citations at all
    scores 0.0, since an uncited concept is not a well-grounded one.
    """
    if not cited_ids:
        return 0.0
    retrieved = set(retrieved_ids)
    return sum(1 for cid in cited_ids if cid in retrieved) / len(cited_ids)


def score_query(
    golden: GoldenQuery, retrieved_ids: list[str], k: int = 5
) -> QueryScore:
    relevant = golden.relevant
    top_k = set(retrieved_ids[:k])
    return QueryScore(
        query=golden.query,
        recall_at_k=recall_at_k(relevant, retrieved_ids, k),
        precision_at_k=precision_at_k(relevant, retrieved_ids, k),
        n_relevant=len(relevant),
        n_retrieved=len(retrieved_ids[:k]),
        n_hit=len(relevant & top_k),
        # The L1 "failure reading" input: what the retriever missed, by id.
        missed_ids=sorted(relevant - top_k),
    )


def summarize(condition: str, scores: list[QueryScore], k: int = 5) -> EvalSummary:
    n = len(scores)
    return EvalSummary(
        condition=condition,
        k=k,
        n_queries=n,
        mean_recall_at_k=sum(s.recall_at_k for s in scores) / n if n else 0.0,
        mean_precision_at_k=sum(s.precision_at_k for s in scores) / n if n else 0.0,
        per_query=scores,
    )


def load_golden_set(path: Path = GOLDEN_SET) -> list[GoldenQuery]:
    """Read the JSONL golden set. Blank lines and `#` comments are skipped."""
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing. The golden set is W2.6 (Human): 20 queries with "
            "3-5 hand-labeled relevant creative IDs each. See "
            "docs/decision-log.md B2 — eval cannot run without it."
        )
    queries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        payload = json.loads(line)
        queries.append(
            GoldenQuery(
                query=payload["query"],
                relevant_creative_ids=payload["relevant_creative_ids"],
                notes=payload.get("notes", ""),
            )
        )
    return queries
