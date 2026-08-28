"""W2.8: one command -> eval results + the semantic-vs-hybrid comparison.

    make eval

Runs the golden set against three conditions — keyword-only (the W1.11
naive baseline), semantic-only, and hybrid — so the Week-2 claim that hybrid
improves on both is a measurement rather than an assertion.

**This has never been run on real data.** The golden set is W2.6 (Human) and
the corpus is nine rows (decision-log B1/B2). The harness is wired and
tested; it refuses to print numbers it cannot stand behind.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from creativesignal.eval.metrics import (
    EvalSummary,
    GoldenQuery,
    load_golden_set,
    score_query,
    summarize,
)

RESULTS_DIR = Path("eval/results")
K = 5

# Below this many golden queries, a mean is noise, not a measurement.
MIN_QUERIES_FOR_REPORTING = 10


def _conditions():
    from creativesignal.retrieval.hybrid import (
        hybrid_search,
        keyword_only_search,
        semantic_only_search,
    )

    return {
        "keyword_only": keyword_only_search,
        "semantic_only": semantic_only_search,
        "hybrid": hybrid_search,
    }


def run_condition(
    name: str, search_fn, golden: list[GoldenQuery], k: int = K
) -> EvalSummary:
    scores = [score_query(g, search_fn(g.query, limit=k).creative_ids, k) for g in golden]
    return summarize(name, scores, k)


def worst_failures(summary: EvalSummary, n: int = 10) -> list:
    """The L1 "failure reading" input: the n worst queries, with what they missed."""
    return sorted(summary.per_query, key=lambda s: (s.recall_at_k, s.precision_at_k))[:n]


def print_table(summaries: list[EvalSummary]) -> None:
    print(f"\n{'condition':<16} {'n':>4} {'recall@' + str(K):>10} {'prec@' + str(K):>10}")
    print("-" * 44)
    for summary in summaries:
        print(
            f"{summary.condition:<16} {summary.n_queries:>4} "
            f"{summary.mean_recall_at_k:>10.3f} {summary.mean_precision_at_k:>10.3f}"
        )


def save_results(summaries: list[EvalSummary], out_dir: Path = RESULTS_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"retrieval_eval_{stamp}.json"
    path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "k": K,
                "summaries": [
                    {**s.as_row(), "per_query": [asdict(q) for q in s.per_query]}
                    for s in summaries
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def main() -> None:
    try:
        golden = load_golden_set()
    except FileNotFoundError as exc:
        print(f"\nCANNOT RUN EVAL:\n{exc}")
        return

    if not golden:
        print("Golden set is empty — nothing to evaluate.")
        return

    summaries = [
        run_condition(name, fn, golden) for name, fn in _conditions().items()
    ]
    print_table(summaries)

    if len(golden) < MIN_QUERIES_FOR_REPORTING:
        print(
            f"\nWARNING: {len(golden)} golden queries is below the "
            f"{MIN_QUERIES_FOR_REPORTING}-query floor. These numbers are "
            "directional at best — do not put them in the README results "
            "table or quote them as measured performance."
        )

    hybrid = next(s for s in summaries if s.condition == "hybrid")
    print("\nWorst retrieval failures (L1 failure reading):")
    for score in worst_failures(hybrid):
        if score.missed_ids:
            print(f"  recall {score.recall_at_k:.2f}  {score.query!r}")
            print(f"    missed: {', '.join(score.missed_ids)}")

    path = save_results(summaries)
    print(f"\nresults -> {path}")
    print(
        "\nCategorize each failure above (wrong filter parse / vocabulary "
        "mismatch / label error / genuinely ambiguous) in docs/decision-log.md."
    )


if __name__ == "__main__":
    main()
