"""Pydantic schema for the two source-of-truth corpus tables.

Split rule (docs/decision-log.md Entry #3): `annotations` holds only fields
where a model exercised judgment. Everything deterministically derived from
observed facts — including the F1 longevity-proxy fields — lives in
`creatives` alongside the raw fields it's derived from.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

SourceType = Literal["tier1", "tier2", "tier3"]
ProxyBucket = Literal["high", "mid", "low"]


class Creative(BaseModel):
    """A source creative record: observed facts + deterministic derivations.

    No field here reflects a model's judgment call — those go in
    `Annotation` instead.
    """

    creative_id: str
    source_type: SourceType
    advertiser: str
    platform: str
    category: str
    headline: Optional[str] = None
    body_copy: Optional[str] = None
    source_url: Optional[str] = None
    date_observed: date
    rights_note: str

    # F1 longevity-proxy fields (implementation.md line 69): deterministic
    # calculations from start_date/date_observed, not model judgment.
    start_date: Optional[date] = None
    days_active: Optional[int] = None
    variant_count: Optional[int] = None
    proxy_bucket: Optional[ProxyBucket] = None


class Annotation(BaseModel):
    """A model's judgment call about a creative.

    One creative may have multiple annotation rows — e.g. an initial
    logistic-regression pass plus an LLM-escalated row for the same
    creative — so `annotation_id` is its own key and `annotator` records
    which pass produced the row.
    """

    annotation_id: str
    creative_id: str
    hook_type: Optional[str] = None
    tone: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    annotator: str
    annotated_at: Optional[datetime] = None


# --- The honesty rule, as a constant ------------------------------------
# Verbatim per AGENTS.md. It appears in the UI footer, the README, and every
# generated report. A constant, not a literal, so it cannot drift between
# the places it's required to be identical.
HONESTY_RULE: str = (
    "Every insight is traceable to examples; every recommendation is a "
    "hypothesis, not a performance claim."
)


def coverage_statement(n_examples: int, descriptive: bool = True) -> str:
    """The mandatory closing line on every report and concept set.

    e.g. "Based on 18 retrieved examples; descriptive, not causal."
    """
    suffix = "descriptive, not causal" if descriptive else "directional only"
    noun = "example" if n_examples == 1 else "examples"
    return f"Based on {n_examples} retrieved {noun}; {suffix}."


# --- Retrieval representations (§8) -------------------------------------


class CreativeCard(BaseModel):
    """The retrieval unit: a structured creative record, never a chunk.

    Two representations per §8 — `card_text` is the assembled factual record,
    `analyst_summary` is an LLM-written characterization of what the ad does.
    Both are embedded; a match on either retrieves the same creative.
    """

    creative_id: str
    card_text: str
    analyst_summary: Optional[str] = None
    # Denormalized for display and metadata filtering at query time.
    advertiser: Optional[str] = None
    platform: Optional[str] = None
    source_url: Optional[str] = None
    date_observed: Optional[date] = None
    hook_type: Optional[str] = None
    tone: Optional[str] = None
    proxy_bucket: Optional[ProxyBucket] = None

    def provenance_line(self) -> str:
        """The one-line footer every card shows in the UI."""
        parts = [
            self.advertiser or "unknown advertiser",
            self.platform or "unknown platform",
            self.date_observed.isoformat() if self.date_observed else "date unknown",
        ]
        return " · ".join(parts)


# --- Generated outputs ---------------------------------------------------


class Pattern(BaseModel):
    """One observed pattern, stated in prevalence terms and cited."""

    description: str
    prevalence_count: int = Field(ge=0)
    total_examined: int = Field(ge=0)
    cited_creative_ids: list[str] = Field(default_factory=list)

    @property
    def prevalence_statement(self) -> str:
        return f"appears in {self.prevalence_count} of {self.total_examined} retrieved examples"


class TrendReport(BaseModel):
    """W3.8: patterns, counter-examples, confidence, coverage statement."""

    query: str
    patterns: list[Pattern] = Field(default_factory=list)
    counter_examples: list[str] = Field(default_factory=list)
    confidence_note: str = ""
    retrieved_creative_ids: list[str] = Field(default_factory=list)
    coverage_statement: str = ""
    generated_at: Optional[datetime] = None

    def ensure_coverage(self) -> TrendReport:
        """Fill the coverage statement if the generator left it blank.

        Required, not optional: a report without one is a report whose
        evidence base is invisible.
        """
        if not self.coverage_statement:
            self.coverage_statement = coverage_statement(len(self.retrieved_creative_ids))
        return self


class Concept(BaseModel):
    """W4.3: one reviewable ad concept with its evidence block."""

    title: str
    hook_type: Optional[str] = None
    headline: str
    body_copy: str
    rationale: str = ""
    cited_creative_ids: list[str] = Field(default_factory=list)
    evidence_note: str = ""
    # Entry #2 defined this field but left it unscheduled; Entry #33 schedules
    # it as the input to local image generation. Defaults to "" so the six
    # runs persisted before this existed still load and replay.
    visual_direction: str = ""
    # Path to a generated image, relative to the repo root. Set only when the
    # user explicitly opts in (Entry #33) — absent is the normal case.
    image_path: Optional[str] = None

    @property
    def is_cited(self) -> bool:
        """A concept with no citation must not ship — the honesty rule."""
        return bool(self.cited_creative_ids)


# --- Reviewer (W4.5) -----------------------------------------------------

FlagSeverity = Literal["claim", "similarity", "info"]
CheckName = Literal[
    "unsupported_claim", "false_scarcity", "prohibited_targeting", "similarity"
]


class ReviewFlag(BaseModel):
    """One reviewer finding, with the evidence that justifies it.

    `evidence` is required: a flag a reviewer can't justify on expand is an
    unexplainable judgment, which is exactly what this project rejects.
    """

    check: CheckName
    severity: FlagSeverity
    message: str
    evidence: str
    span: Optional[str] = None
    related_creative_ids: list[str] = Field(default_factory=list)


class ReviewResult(BaseModel):
    """The independent reviewer's structured verdict on one concept."""

    concept_title: str
    flags: list[ReviewFlag] = Field(default_factory=list)
    checks_run: list[str] = Field(default_factory=list)
    reviewed_at: Optional[datetime] = None

    @property
    def passed(self) -> bool:
        """No claim-severity flags. Similarity and info do not block."""
        return not any(flag.severity == "claim" for flag in self.flags)

    def flags_for(self, check: str) -> list[ReviewFlag]:
        return [flag for flag in self.flags if flag.check == check]


# --- Persistence (W4.6b) -------------------------------------------------


class Run(BaseModel):
    """A persisted brief->concepts generation, replayable in demo mode (W6.1b)."""

    run_id: str
    created_at: datetime
    brief: dict = Field(default_factory=dict)
    retrieved_creative_ids: list[str] = Field(default_factory=list)
    trend_report: Optional[TrendReport] = None
    concepts: list[Concept] = Field(default_factory=list)
    review_results: list[ReviewResult] = Field(default_factory=list)
    model_versions: dict[str, str] = Field(default_factory=dict)
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    token_cost_usd: float = 0.0

    # `model_versions` starts with "model_", which Pydantic protects by default.
    model_config = {"protected_namespaces": ()}
