"""W3.3: agent bounds, coverage gate, citation self-check (Entry #14)."""

from __future__ import annotations

from datetime import date

import pytest

from creativesignal.agents import analyst as analyst_module
from creativesignal.agents.analyst import (
    MIN_COVERAGE,
    Brief,
    build_trend_report,
    run_analyst,
    self_check_citations,
)
from creativesignal.ingest.build_corpus import build_corpus, insert_creatives
from creativesignal.schema import Concept, Creative, Pattern
from creativesignal.tracing import AgentTrace


@pytest.fixture
def corpus(tmp_path):
    db = tmp_path / "corpus.sqlite"
    build_corpus(db)
    insert_creatives(
        [
            Creative(
                creative_id=f"c{i}",
                source_type="tier2",
                advertiser="synthetic (no advertiser)",
                platform="unknown",
                category="skincare",
                headline=f"Gentle Cleanser {i}",
                body_copy="A gentle daily cleanser for sensitive skin.",
                date_observed=date(2026, 8, 28),
                rights_note="local use only",
            )
            for i in range(5)
        ],
        db,
    )
    return db


# --- brief ----------------------------------------------------------------


def test_brief_flattens_the_fields_that_describe_the_ad():
    brief = Brief(text="hydrating serum", audience="women 25-40", tone="clinical",
                  objective="awareness")
    query = brief.as_query()
    assert "hydrating serum" in query and "women 25-40" in query
    assert "awareness" not in query  # objective is not a retrieval signal


def test_thin_brief_needs_clarification():
    assert Brief(text="serum").needs_clarification


def test_brief_with_audience_does_not_need_clarification():
    assert not Brief(text="serum", audience="women 25-40").needs_clarification


# --- coverage gate --------------------------------------------------------


def test_thin_brief_returns_one_clarifying_question(corpus):
    result = run_analyst(Brief(text="serum"), db_path=corpus, with_concepts=False)
    assert result.clarifying_question is not None
    assert not result.coverage_ok
    assert result.trend_report.patterns == []


def test_below_coverage_floor_reports_the_gap_instead_of_patterns(corpus):
    """The honest failure mode — no invented patterns."""
    result = run_analyst(
        Brief(text="cryptocurrency trading platform", audience="traders"),
        db_path=corpus,
        with_concepts=False,
    )
    assert not result.coverage_ok
    assert result.trend_report.patterns == []
    assert "Insufficient coverage" in result.trend_report.confidence_note
    assert str(MIN_COVERAGE) in result.trend_report.confidence_note


def test_sufficient_coverage_runs_the_full_pipeline(corpus):
    result = run_analyst(
        Brief(text="gentle cleanser for sensitive skin", audience="women 25-40"),
        db_path=corpus,
        with_concepts=False,
    )
    assert result.coverage_ok
    assert len(result.retrieved_ids) >= MIN_COVERAGE
    assert "Directional" in result.trend_report.confidence_note


# --- trace ----------------------------------------------------------------


def test_trace_records_every_step_in_order(corpus):
    result = run_analyst(
        Brief(text="gentle cleanser for sensitive skin", audience="women"),
        db_path=corpus,
        with_concepts=False,
    )
    names = [s.name for s in result.trace.steps]
    assert names[:3] == ["interpret_brief", "search_creatives", "coverage_check"]
    assert all(s.duration_s >= 0 for s in result.trace.steps)


def test_trace_step_records_errors_and_reraises():
    trace = AgentTrace()
    with pytest.raises(ValueError):
        with trace.step("boom"):
            raise ValueError("kaboom")
    assert trace.steps[0].error.startswith("ValueError")


# --- report assembly ------------------------------------------------------


def test_report_always_carries_a_coverage_statement():
    report = build_trend_report("q", [], ["a", "b", "c"], coverage_ok=True)
    assert report.coverage_statement == "Based on 3 retrieved examples; descriptive, not causal."


def test_universal_pattern_is_surfaced_as_a_counter_example():
    """A pattern in every example doesn't distinguish between them."""
    pattern = Pattern(
        description="hook_type = offer_led", prevalence_count=5, total_examined=5
    )
    report = build_trend_report("q", [pattern], ["a"] * 5, coverage_ok=True)
    assert report.counter_examples
    assert "does not distinguish" in report.counter_examples[0]


def test_non_universal_pattern_is_not_a_counter_example():
    pattern = Pattern(
        description="hook_type = offer_led", prevalence_count=3, total_examined=5
    )
    assert build_trend_report("q", [pattern], ["a"] * 5, coverage_ok=True).counter_examples == []


# --- citation self-check (the honesty gate) ------------------------------


def test_concept_citing_an_unretrieved_id_is_dropped():
    concept = Concept(title="Ghost", headline="h", body_copy="b",
                      cited_creative_ids=["c1", "ghost"])
    kept, dropped = self_check_citations([concept], ["c1", "c2"])
    assert kept == []
    assert "cited unretrieved" in dropped[0]


def test_uncited_concept_is_dropped():
    concept = Concept(title="Bare", headline="h", body_copy="b", cited_creative_ids=[])
    kept, dropped = self_check_citations([concept], ["c1"])
    assert kept == []
    assert "no citations" in dropped[0]


def test_properly_cited_concept_survives():
    concept = Concept(title="Good", headline="h", body_copy="b",
                      cited_creative_ids=["c1"])
    kept, dropped = self_check_citations([concept], ["c1", "c2"])
    assert [c.title for c in kept] == ["Good"]
    assert dropped == []


def test_self_check_runs_in_the_pipeline_and_notes_drops(corpus, monkeypatch):
    """A hallucinated citation is dropped by the agent, not just by eval."""
    def _fake_generate(brief, evidence_ids, n_concepts=3, db_path=None):
        return [
            Concept(title="Ghost", headline="h", body_copy="b",
                    cited_creative_ids=["not_retrieved"]),
            Concept(title="Real", headline="h", body_copy="b",
                    cited_creative_ids=[evidence_ids[0]]),
        ]

    monkeypatch.setattr(analyst_module, "generate_concepts", _fake_generate)
    result = run_analyst(
        Brief(text="gentle cleanser for sensitive skin", audience="women"),
        db_path=corpus,
    )
    assert [c.title for c in result.concepts] == ["Real"]
    assert any("Ghost" in note for note in result.trace.notes)
