"""W1.4: hand-curated Meta Ad Library sample -> normalized `Creative` records.

Tier-3 is the provenance-rich core: the only tier with a real advertiser, a
resolvable ad-library URL, an observation date, and the F1 longevity-proxy
fields. It is also the only tier the W3.6 insight tree trains on.

**The curated file does not exist yet** (W0.3, Human — decision-log B1). This
loader is built against the 14-column curation template and returns an empty
list with a clear message when the file is absent, so the ingest path stays
runnable and picks the data up with no code change.

`days_active` and `proxy_bucket` are recomputed here rather than trusted from
the sheet: per decision-log Entry #3 they are deterministic derivations, so
the source fields (`start_date`, `date_observed`) are authoritative and the
derived columns are a convenience for the human curator.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from creativesignal.schema import Creative, ProxyBucket

TIER3_CSV = Path("data/raw/tier3_meta_sample.csv")

# Columns the curation template guarantees (W0.3).
REQUIRED_COLUMNS: tuple[str, ...] = (
    "creative_id", "advertiser", "ad_library_url", "platform", "category",
    "headline", "body_copy", "start_date", "date_observed", "variant_count",
    "source_type", "rights_note",
)

# F1 longevity-proxy thresholds, RECALIBRATED against the delivered Tier-3
# data — decision-log Entry #23, which is the recalibration Entry #5 required
# before the tree could be trained.
#
# Still fixed rather than percentile-based, so a record's bucket never changes
# when the corpus around it changes (Entry #3 requires proxy_bucket to be
# deterministic from its source fields). The values are now *informed* by the
# observed distribution (true tertiles 8.0 and 22.7 days) rather than guessed:
# <10 / 10-24 / >=25 splits the 95 curated ads 36 / 31 / 28.
HIGH_DAYS = 25
LOW_DAYS = 10


def compute_days_active(start: date | None, observed: date | None) -> int | None:
    """Days between the ad's Ad Library start date and when we observed it."""
    if start is None or observed is None:
        return None
    return max((observed - start).days, 0)


def compute_proxy_bucket(
    days_active: int | None, variant_count: int | None = None
) -> ProxyBucket | None:
    """Bucket the longevity proxy into high / mid / low.

    Descriptive only: a long-running ad is one the advertiser kept paying for.
    That is a spend-persistence signal, not a performance measurement, and
    nothing downstream may describe it as one.

    `variant_count` is accepted but **deliberately unused** — in the delivered
    curation it is the constant 20 for all 95 rows, so it carries no
    information and, under the original rule, forced every ad into `high`.
    See Entry #23. The parameter is kept so the signature survives a corrected
    re-curation without a call-site change.
    """
    if days_active is None:
        return None
    if days_active >= HIGH_DAYS:
        return "high"
    if days_active < LOW_DAYS:
        return "low"
    return "mid"


# Curation is hand-typed, so `category` arrives with mixed case and at least
# one typo. Normalized at load rather than corrected in the source file: the
# CSV is the human's artifact, and silently editing it would make their
# curation and the loaded corpus disagree.
CATEGORY_ALIASES: dict[str, str] = {
    "deodrant": "deodorant",  # typo in the curated sheet
    "spf": "sunscreen",
    "lip balm": "lip balm",
}


def normalize_category(value: Any) -> str:
    """Lowercase, strip, and fix known spellings. Blank -> uncategorized."""
    import pandas as pd

    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "uncategorized"
    text = str(value).strip().lower()
    if not text or text == "nan":
        return "uncategorized"
    return CATEGORY_ALIASES.get(text, text)


def clean_body_copy(value: Any) -> str | None:
    """Drop ad copy that is an unrendered template, not text.

    Four curated rows carry a literal `{{product.brand}}` — the ad library
    captured the template variable rather than its value. That string is not
    ad copy: indexing it would put a meaningless token in the corpus and let
    those rows match queries for reasons unrelated to their content. The row
    is kept (its provenance and proxy fields are real and the tree uses them);
    only the unusable copy is nulled.
    """
    import pandas as pd

    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    # A body that is *entirely* placeholders carries no content.
    without_placeholders = re.sub(r"\{\{[^}]*\}\}", "", text).strip()
    return without_placeholders or None


def _coerce_date(value: Any) -> date | None:
    import pandas as pd

    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    ts = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(ts) else ts.date()


def _coerce_int(value: Any) -> int | None:
    import pandas as pd

    if value is None or pd.isna(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _read_frame(path: Path):
    import pandas as pd

    # The human curates in Excel; the spec names a CSV. Accept either.
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def load_tier3(path: Path = TIER3_CSV) -> list[Creative]:
    """Load the curated sample. Returns [] (with a message) if not yet curated."""
    import pandas as pd

    if not path.exists():
        print(
            f"  Tier-3 not curated yet: {path} missing. Skipping. "
            "This is W0.3 (Human) — see docs/decision-log.md B1. The insight "
            "tree (W3.6) and all eval numbers depend on it."
        )
        return []

    df = _read_frame(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"{path} is missing required column(s): {missing}. "
            f"Expected the W0.3 curation template columns: {list(REQUIRED_COLUMNS)}"
        )

    out: list[Creative] = []
    for _, row in df.iterrows():
        start = _coerce_date(row["start_date"])
        observed = _coerce_date(row["date_observed"])
        if observed is None:
            raise ValueError(
                f"Row {row['creative_id']!r} has no usable date_observed — "
                "it is required provenance, not an optional field."
            )
        variant_count = _coerce_int(row["variant_count"])
        days_active = compute_days_active(start, observed)

        rights_note = str(row["rights_note"]) if not pd.isna(row["rights_note"]) else ""
        out.append(
            Creative(
                creative_id=str(row["creative_id"]),
                source_type="tier3",
                advertiser=str(row["advertiser"]),
                platform=str(row["platform"]),
                # Blank category/rights_note fall back rather than drop the
                # record, and the gap stays legible.
                category=normalize_category(row["category"]),
                headline=None if pd.isna(row["headline"]) else str(row["headline"]),
                body_copy=clean_body_copy(row["body_copy"]),
                source_url=(
                    None if pd.isna(row["ad_library_url"])
                    else str(row["ad_library_url"])
                ),
                date_observed=observed,
                rights_note=rights_note or "RIGHTS NOTE MISSING — review before publication",
                start_date=start,
                days_active=days_active,
                variant_count=variant_count,
                proxy_bucket=compute_proxy_bucket(days_active, variant_count),
            )
        )
    return out
