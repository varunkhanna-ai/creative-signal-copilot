"""W2.8/W4.8: metric formulas. These are the numbers the README will quote.

Every case here is one an interviewer could ask about — the denominators in
particular, which are where Entry #11's counting rule lives.
"""

from __future__ import annotations

import pytest

from creativesignal.eval.metrics import (
    GoldenQuery,
    citation_correctness,
    load_golden_set,
    precision_at_k,
    recall_at_k,
    score_query,
    summarize,
)


# --- recall ---------------------------------------------------------------


def test_recall_counts_hits_over_all_relevant():
    assert recall_at_k({"a", "b", "c", "d"}, ["a", "b", "x", "y", "z"], k=5) == 0.5


def test_recall_ignores_results_past_k():
    """The 'at k' is the whole point — a hit at rank 6 is not a hit at 5."""
    assert recall_at_k({"a"}, ["x", "y", "z", "w", "v", "a"], k=5) == 0.0


def test_perfect_recall():
    assert recall_at_k({"a", "b"}, ["a", "b", "c"], k=5) == 1.0


def test_recall_with_no_relevant_documents_is_zero_not_an_error():
    """A mislabeled golden query must not silently inflate the mean."""
    assert recall_at_k(set(), ["a", "b"], k=5) == 0.0


def test_recall_with_no_results():
    assert recall_at_k({"a"}, [], k=5) == 0.0


# --- precision ------------------------------------------------------------


def test_precision_divides_by_results_actually_returned():
    """Entry #11: not a literal k. Three returned, two relevant -> 2/3."""
    assert precision_at_k({"a", "b"}, ["a", "b", "x"], k=5) == pytest.approx(2 / 3)


def test_precision_does_not_penalize_a_small_corpus():
    """One result returned, and it's relevant, is precision 1.0 — not 0.2."""
    assert precision_at_k({"a"}, ["a"], k=5) == 1.0


def test_precision_truncates_at_k():
    assert precision_at_k({"a", "f"}, ["a", "b", "c", "d", "e", "f"], k=5) == 0.2


def test_precision_with_no_results():
    assert precision_at_k({"a"}, [], k=5) == 0.0


# --- citation correctness (W4.8) -----------------------------------------


def test_citation_correctness_all_real():
    assert citation_correctness(["a", "b"], ["a", "b", "c"]) == 1.0


def test_citation_correctness_catches_a_hallucinated_id():
    """The specific failure the honesty rule forbids."""
    assert citation_correctness(["a", "ghost"], ["a", "b"]) == 0.5


def test_uncited_output_scores_zero():
    """An uncited concept is not a well-grounded one."""
    assert citation_correctness([], ["a", "b"]) == 0.0


def test_citation_correctness_all_hallucinated():
    assert citation_correctness(["x", "y"], ["a", "b"]) == 0.0


# --- per-query scoring ----------------------------------------------------


def test_score_query_records_what_was_missed():
    """The L1 failure-reading input — the metric alone doesn't tell you why."""
    golden = GoldenQuery("gentle cleanser", ["a", "b", "c"])
    score = score_query(golden, ["a", "x", "y"], k=5)
    assert score.n_hit == 1
    assert score.missed_ids == ["b", "c"]
    assert score.recall_at_k == pytest.approx(1 / 3)


def test_duplicate_ids_in_results_do_not_double_count():
    """Entry #11: a creative counts once however many representations hit."""
    golden = GoldenQuery("q", ["a"])
    score = score_query(golden, ["a", "a", "b"], k=5)
    assert score.n_hit == 1
    assert score.recall_at_k == 1.0


# --- aggregation ----------------------------------------------------------


def test_summarize_averages_and_keeps_sample_size():
    scores = [
        score_query(GoldenQuery("q1", ["a"]), ["a"], k=5),      # recall 1.0
        score_query(GoldenQuery("q2", ["b"]), ["x"], k=5),      # recall 0.0
    ]
    summary = summarize("hybrid", scores, k=5)
    assert summary.n_queries == 2
    assert summary.mean_recall_at_k == 0.5
    assert summary.as_row()["condition"] == "hybrid"


def test_summarize_of_nothing_does_not_divide_by_zero():
    assert summarize("hybrid", [], k=5).mean_recall_at_k == 0.0


# --- golden set loading ---------------------------------------------------


def test_missing_golden_set_names_the_owning_task():
    from pathlib import Path

    with pytest.raises(FileNotFoundError, match="W2.6"):
        load_golden_set(Path("does/not/exist.jsonl"))


def test_golden_set_skips_comments_and_blank_lines(tmp_path):
    path = tmp_path / "golden.jsonl"
    path.write_text(
        '# a comment\n\n{"query": "q", "relevant_creative_ids": ["a", "b"]}\n'
    )
    [query] = load_golden_set(path)
    assert query.query == "q"
    assert query.relevant == {"a", "b"}


def test_committed_golden_set_is_still_the_unbuilt_template(tmp_path):
    """Guards against the format spec being mistaken for real data (W2.6)."""
    assert load_golden_set() == []
