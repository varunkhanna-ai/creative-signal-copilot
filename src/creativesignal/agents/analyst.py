"""W3.3/W3.8/W4.3: the Creative Analyst agent.

A plain Python function, not a framework (AGENTS.md). Fixed pipeline per
decision-log Entry #14:

    interpret brief -> filters -> retrieve -> coverage check -> analyze
    patterns -> synthesize cited report -> self-check claims -> concepts

Every step lands in an `AgentTrace`, which the UI renders and Phoenix
mirrors. The coverage check and the citation self-check are the two places
the honesty rule is enforced as a gate rather than as prompt wording.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from creativesignal.agents.tools import (
    analyze_pattern,
    generate_concepts,
    search_creatives,
)
from creativesignal.schema import (
    Concept,
    Pattern,
    TrendReport,
    coverage_statement,
)
from creativesignal.sources.curated import DB_PATH
from creativesignal.tracing import AgentTrace

# Entry #14 bounds.
MAX_TOOL_CALLS = 8
MIN_COVERAGE = 3
DEFAULT_RETRIEVE = 8


@dataclass
class Brief:
    """A campaign brief. Only `text` is required; the rest sharpen retrieval."""

    text: str
    audience: str = ""
    objective: str = ""
    tone: str = ""
    prohibited_claims: str = ""

    def as_query(self) -> str:
        """Flatten to a retrieval query — the fields that describe the ad."""
        return " ".join(p for p in (self.text, self.audience, self.tone) if p).strip()

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "audience": self.audience,
            "objective": self.objective,
            "tone": self.tone,
            "prohibited_claims": self.prohibited_claims,
        }

    @property
    def needs_clarification(self) -> bool:
        """Entry #14: ask only when both product context and audience are absent."""
        return not self.audience.strip() and len(self.text.split()) < 4


@dataclass
class AnalystResult:
    """Everything one run produced, including how it produced it."""

    brief: Brief
    trend_report: TrendReport
    concepts: list[Concept] = field(default_factory=list)
    retrieved_ids: list[str] = field(default_factory=list)
    trace: AgentTrace = field(default_factory=AgentTrace)
    clarifying_question: str | None = None
    coverage_ok: bool = True


class ToolBudgetExceeded(RuntimeError):
    """Raised rather than silently truncating — see Entry #14."""


def _check_budget(trace: AgentTrace) -> None:
    if trace.tool_call_count >= MAX_TOOL_CALLS:
        raise ToolBudgetExceeded(
            f"Agent exceeded {MAX_TOOL_CALLS} tool calls. A partial report that "
            "looks complete is worse than an error."
        )


def build_trend_report(
    query: str, patterns: list[Pattern], retrieved_ids: list[str], coverage_ok: bool
) -> TrendReport:
    """Assemble the report. Confidence wording is derived, never model-authored."""
    if not coverage_ok:
        confidence = (
            f"Insufficient coverage: {len(retrieved_ids)} examples retrieved, "
            f"below the {MIN_COVERAGE}-example floor. No prevalence pattern is "
            "reported, because a count over this few examples is noise rather "
            "than a pattern."
        )
    else:
        confidence = (
            f"Directional. Based on {len(retrieved_ids)} retrieved examples from "
            "a curated corpus; prevalence within this set, not evidence of "
            "performance."
        )

    # A pattern present in every example is not a distinguishing pattern —
    # surfacing it as a counter-example keeps the report honest about that.
    counter_examples = [
        f"{p.description} appears in all {p.total_examined} examples, so it "
        "does not distinguish between them."
        for p in patterns
        if p.total_examined and p.prevalence_count == p.total_examined
    ]

    return TrendReport(
        query=query,
        patterns=patterns if coverage_ok else [],
        counter_examples=counter_examples,
        confidence_note=confidence,
        retrieved_creative_ids=retrieved_ids,
        coverage_statement=coverage_statement(len(retrieved_ids)),
        generated_at=datetime.now(timezone.utc),
    ).ensure_coverage()


def self_check_citations(
    concepts: list[Concept], retrieved_ids: list[str]
) -> tuple[list[Concept], list[str]]:
    """Drop concepts citing anything outside the evidence set.

    A gate, not a warning label (Entry #14): "traceable to examples" is false
    if the example was invented, so the concept does not ship.
    """
    allowed = set(retrieved_ids)
    kept, dropped = [], []
    for concept in concepts:
        invented = [cid for cid in concept.cited_creative_ids if cid not in allowed]
        if invented or not concept.is_cited:
            dropped.append(
                f"{concept.title!r} dropped: "
                + (f"cited unretrieved {invented}" if invented else "no citations")
            )
        else:
            kept.append(concept)
    return kept, dropped


def run_analyst(
    brief: Brief,
    n_concepts: int = 3,
    limit: int = DEFAULT_RETRIEVE,
    db_path: Path = DB_PATH,
    with_concepts: bool = True,
) -> AnalystResult:
    """Run the full brief -> evidence -> report -> concepts pipeline."""
    trace = AgentTrace()

    # 1. Interpret the brief.
    with trace.step("interpret_brief", brief=brief.text) as step:
        query = brief.as_query()
        step.output_summary = f"query={query!r}"

    if brief.needs_clarification:
        trace.note("Brief lacks both audience and product detail — asking once.")
        return AnalystResult(
            brief=brief,
            trend_report=build_trend_report(query, [], [], coverage_ok=False),
            trace=trace,
            coverage_ok=False,
            clarifying_question=(
                "Which product or skin concern is this campaign for, and who is "
                "the intended audience? The corpus is filtered by both, so "
                "retrieval will be thin without them."
            ),
        )

    # 2. Retrieve.
    _check_budget(trace)
    with trace.step("search_creatives", query=query, limit=limit) as step:
        found = search_creatives(query, limit=limit, db_path=db_path)
        retrieved_ids = [hit.creative_id for hit in found.hits]
        step.output_summary = f"{len(retrieved_ids)} creatives: {retrieved_ids}"

    # 3. Coverage check — the honest failure mode.
    coverage_ok = len(retrieved_ids) >= MIN_COVERAGE
    with trace.step("coverage_check", retrieved=len(retrieved_ids)) as step:
        step.output_summary = (
            f"{len(retrieved_ids)} >= {MIN_COVERAGE}: {'pass' if coverage_ok else 'FAIL'}"
        )
    if not coverage_ok:
        trace.note(
            f"Coverage below {MIN_COVERAGE}. Reporting the gap instead of "
            "inventing patterns."
        )
        return AnalystResult(
            brief=brief,
            trend_report=build_trend_report(query, [], retrieved_ids, coverage_ok=False),
            retrieved_ids=retrieved_ids,
            trace=trace,
            coverage_ok=False,
        )

    # 4. Prevalence over both annotation axes.
    patterns: list[Pattern] = []
    for dimension in ("hook_type", "tone"):
        _check_budget(trace)
        with trace.step("analyze_pattern", dimension=dimension) as step:
            analysis = analyze_pattern(retrieved_ids, dimension, db_path=db_path)
            patterns.extend(analysis.patterns)
            step.output_summary = f"{len(analysis.patterns)} {dimension} values"
    if not patterns:
        trace.note(
            "No annotations available, so no prevalence patterns could be "
            "computed. Run `make annotate` (needs an API key)."
        )

    # 5. Synthesize.
    with trace.step("build_trend_report", patterns=len(patterns)) as step:
        report = build_trend_report(query, patterns, retrieved_ids, coverage_ok=True)
        step.output_summary = f"{len(report.patterns)} patterns, coverage attached"

    # 6. Concepts, then the citation self-check.
    concepts: list[Concept] = []
    if with_concepts:
        _check_budget(trace)
        with trace.step("generate_concepts", n=n_concepts) as step:
            concepts = generate_concepts(
                brief.text, retrieved_ids, n_concepts=n_concepts, db_path=db_path
            )
            step.output_summary = f"{len(concepts)} concepts returned"

        with trace.step("self_check_citations", n=len(concepts)) as step:
            concepts, dropped = self_check_citations(concepts, retrieved_ids)
            step.output_summary = f"{len(concepts)} kept, {len(dropped)} dropped"
            for message in dropped:
                trace.note(message)

    return AnalystResult(
        brief=brief,
        trend_report=report,
        concepts=concepts,
        retrieved_ids=retrieved_ids,
        trace=trace,
        coverage_ok=True,
    )
