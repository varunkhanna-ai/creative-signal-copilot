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
    # v3 constrains visual_direction to product-only framing (Entry #38);
    # v2 added the field (Entry #34); v1 produced the six oldest runs. The
    # stamp is per-run precisely so those stay correctly attributed.
    assert run.prompt_versions["concepts"] == "concept_v3"


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


# --- image persistence (Entry #33) ----------------------------------------


def test_image_path_round_trips_through_sqlite(tmp_path, run):
    """`image_path` rides along in the concept JSON — no schema migration."""
    from creativesignal.runs import attach_image

    db = tmp_path / "corpus.sqlite"
    save_run(run, db)
    ok = attach_image(
        run.run_id, "Ceramide night repair", "data/generated_images/x/y.png", db
    )
    assert ok is True

    reloaded = load_run(run.run_id, db)
    assert reloaded.concepts[0].image_path == "data/generated_images/x/y.png"


def test_attach_image_leaves_concept_text_untouched(tmp_path, run):
    """Attaching an image must never alter content the reviewer already passed."""
    from creativesignal.runs import attach_image

    db = tmp_path / "corpus.sqlite"
    save_run(run, db)
    before = run.concepts[0]
    attach_image(run.run_id, before.title, "img.png", db)
    after = load_run(run.run_id, db).concepts[0]

    assert after.headline == before.headline
    assert after.body_copy == before.body_copy
    assert after.rationale == before.rationale
    assert after.cited_creative_ids == before.cited_creative_ids


def test_attach_image_reports_an_unknown_run(tmp_path):
    from creativesignal.runs import attach_image

    assert attach_image("run_nope", "T", "img.png", tmp_path / "corpus.sqlite") is False


def test_attach_image_reports_an_unknown_concept(tmp_path, run):
    from creativesignal.runs import attach_image

    db = tmp_path / "corpus.sqlite"
    save_run(run, db)
    assert attach_image(run.run_id, "No Such Concept", "img.png", db) is False


def test_concepts_without_images_default_to_none(tmp_path, run):
    """The six runs persisted before Entry #33 have no image_path at all."""
    db = tmp_path / "corpus.sqlite"
    save_run(run, db)
    assert load_run(run.run_id, db).concepts[0].image_path is None
