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
