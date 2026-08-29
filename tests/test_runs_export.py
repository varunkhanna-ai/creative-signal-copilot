"""W4.6b/W4.7: run persistence round-trip and Markdown export."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from creativesignal.export import export_filename, run_to_markdown
from creativesignal.runs import build_run, list_runs, load_run, save_run
from creativesignal.schema import (
    Concept,
    Pattern,
    ReviewFlag,
    ReviewResult,
    TrendReport,
)


@pytest.fixture
def run():
    return build_run(
        brief={"text": "hydrating serum", "audience": "women 25-40"},
        retrieved_creative_ids=["c1", "c2"],
        trend_report=TrendReport(
            query="hydrating serum",
            patterns=[
                Pattern(
                    description="hook_type = ingredient_led",
                    prevalence_count=2,
                    total_examined=2,
                    cited_creative_ids=["c1", "c2"],
                )
            ],
            counter_examples=["appears in all 2 examples"],
            confidence_note="Directional.",
            retrieved_creative_ids=["c1", "c2"],
            coverage_statement="Based on 2 retrieved examples; descriptive, not causal.",
        ),
        concepts=[
            Concept(
                title="Ceramide night repair",
                hook_type="ingredient_led",
                headline="Ceramides while you sleep",
                body_copy="Supports your skin barrier overnight.",
                rationale="Ingredient-led opening appears in 2 of 2 retrieved examples.",
                cited_creative_ids=["c1"],
                evidence_note="c1 opens on a named ingredient.",
            )
        ],
        review_results=[
            ReviewResult(
                concept_title="Ceramide night repair",
                flags=[
                    ReviewFlag(
                        check="similarity",
                        severity="similarity",
                        message="65% similar to c1.",
                        evidence="Jaccard 0.65. Shared terms: ceramides, barrier.",
                        related_creative_ids=["c1"],
                    )
                ],
                checks_run=["unsupported_claim", "similarity"],
            )
        ],
        token_cost_usd=0.0123,
    )


# --- persistence ----------------------------------------------------------


def test_run_round_trips_through_sqlite(tmp_path, run):
    db = tmp_path / "corpus.sqlite"
    save_run(run, db)
    loaded = load_run(run.run_id, db)

    assert loaded is not None
    assert loaded.run_id == run.run_id
    assert loaded.brief == run.brief
    assert loaded.retrieved_creative_ids == ["c1", "c2"]
    assert loaded.trend_report.patterns[0].prevalence_count == 2
    assert loaded.concepts[0].title == "Ceramide night repair"
    assert loaded.review_results[0].flags[0].check == "similarity"
    assert loaded.token_cost_usd == pytest.approx(0.0123)


def test_load_unknown_run_returns_none(tmp_path):
    assert load_run("run_nope", tmp_path / "corpus.sqlite") is None


def test_list_runs_is_newest_first(tmp_path, run):
    db = tmp_path / "corpus.sqlite"
    older = run.model_copy(
        update={"run_id": "run_old", "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    )
    save_run(older, db)
    save_run(run, db)
    assert [r.run_id for r in list_runs(db_path=db)] == [run.run_id, "run_old"]


def test_run_records_model_and_prompt_versions(run):
    """L3 prompt A/B needs to know which prompt produced which output."""
    assert run.model_versions["synthesis"]
    assert run.prompt_versions["concepts"] == "concept_v1"


def test_saving_twice_replaces_rather_than_duplicates(tmp_path, run):
    db = tmp_path / "corpus.sqlite"
    save_run(run, db)
    save_run(run, db)
    assert len(list_runs(db_path=db)) == 1


# --- export ---------------------------------------------------------------


def test_markdown_contains_the_honesty_rule_verbatim(run):
    markdown = run_to_markdown(run)
    assert (
        "Every insight is traceable to examples; every recommendation is a "
        "hypothesis, not a performance claim." in markdown
    )


def test_markdown_carries_coverage_statement_and_citations(run):
    markdown = run_to_markdown(run)
    assert "descriptive, not causal" in markdown
    assert "`c1`" in markdown


def test_markdown_includes_reviewer_flags_with_evidence(run):
    """An export that dropped the flags would misrepresent the work."""
    markdown = run_to_markdown(run)
    assert "[SIMILARITY]" in markdown
    assert "Jaccard 0.65" in markdown


def test_markdown_renders_source_links_when_available(run):
    markdown = run_to_markdown(run, source_urls={"c1": "https://example.com/ad/1"})
    assert "[source](https://example.com/ad/1)" in markdown


def test_markdown_is_explicit_when_there_is_no_source_link(run):
    assert "no source link (synthetic corpus)" in run_to_markdown(run)


def test_markdown_handles_a_run_with_no_concepts(run):
    empty = run.model_copy(update={"concepts": [], "review_results": []})
    assert "No concepts passed the citation self-check." in run_to_markdown(empty)


def test_export_filename_is_stable_and_identifies_the_run(run):
    name = export_filename(run)
    assert name.endswith(".md")
    assert run.run_id in name
