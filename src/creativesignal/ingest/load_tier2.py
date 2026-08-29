"""W1.4: Tier-2 ad-copy datasets -> normalized `Creative` records.

Two datasets with different shapes, one output type. Both are *synthetic*
generated ad copy, not observed live ads, so every row here carries:
  - no `source_url` (there is no ad to link to),
  - no F1 proxy fields (nothing ran, so nothing has a duration),
  - a `rights_note` naming the undeclared license (docs/data-governance.md).

The skincare filter is the vertical (decision-log Entry #1) applied as a
keyword match over product + description + ad text. Yield is low by design —
these are general-purpose ad corpora, not beauty corpora.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from creativesignal.schema import Creative

RAW_DIR = Path("data/raw/tier2_adcopy")

# Frozen at W1.4. Matched case-insensitively against product+description+ad.
SKINCARE_KEYWORDS: tuple[str, ...] = (
    "skincare", "skin care", "serum", "moisturiz", "cleanser", "sunscreen",
    "spf", "retinol", "acne", "wrinkle", "anti-aging", "anti aging", "toner",
    "exfoliat", "hyaluronic", "collagen", "dermat", "face cream", "face wash",
    "eye cream",
)

# Matched against the *product name only*, which is what actually determines
# category. Without this, "wrinkle" pulls in garment steamers and clothes
# irons (wrinkle-free shirts) and "serum" pulls in hair serum — 4 of the
# first 24 matches were these false positives. See decision-log Entry #7.
NON_SKINCARE_PRODUCTS: tuple[str, ...] = (
    "iron", "steamer", "garment", "clothing", "fabric", "laundry", "hair",
    "shampoo", "conditioner",
)

_RIGHTS = {
    "ad-copy-generation": (
        "Synthetic ad copy, smangrul/ad-copy-generation. License UNDECLARED on "
        "the HF card — local use only, not redistributed, not quoted verbatim "
        "in published artifacts. See docs/data-governance.md."
    ),
    "advertisement-copy": (
        "Synthetic ad copy, jaykin01/advertisement-copy. License declared "
        "'unknown' on the HF card — local use only, not redistributed, not "
        "quoted verbatim in published artifacts. See docs/data-governance.md."
    ),
}

# `Product: X\nDescription: Y [/INST] Ad: Z </s>` — the Llama-2 instruction
# format smangrul packs all three fields into.
_SMANGRUL_RE = re.compile(
    r"Product:\s*(?P<product>.*?)\s*\n"
    r"Description:\s*(?P<description>.*?)\s*\[/INST\]\s*"
    r"Ad:\s*(?P<ad>.*?)\s*(?:</s>)?\s*$",
    re.DOTALL,
)


def is_skincare(product: str | None, *texts: str | None) -> bool:
    """True if the row is a skincare ad.

    Two-step: the product name must not name a non-skincare category, then any
    skincare keyword may appear anywhere in the row. Ordering matters — the
    exclusion is a veto, because product name is the category signal and the
    body copy is where the misleading keyword overlap lives.
    """
    product_l = (product or "").lower()
    if any(bad in product_l for bad in NON_SKINCARE_PRODUCTS):
        return False
    blob = " ".join(t for t in (product, *texts) if t).lower()
    return any(kw in blob for kw in SKINCARE_KEYWORDS)


def _dedupe_key(creative: Creative) -> str:
    """Normalized body copy — the field that actually carries the ad."""
    return " ".join((creative.body_copy or "").lower().split())


def dedupe(creatives: list[Creative]) -> list[Creative]:
    """Drop creatives whose ad copy duplicates an earlier one.

    The two Tier-2 datasets overlap heavily — many rows are byte-identical
    across them, so an undeduped corpus double-counts the same ad under two
    ids. That would inflate every retrieval metric (the same text matching
    twice looks like two relevant results) and let a duplicate be "retrieved
    evidence" for itself. First occurrence wins. See decision-log Entry #7.
    """
    seen: set[str] = set()
    out: list[Creative] = []
    for creative in creatives:
        key = _dedupe_key(creative)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(creative)
    return out


def _load_parquet(path: Path):
    import pandas as pd

    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing — run `make download` first (W0.4)."
        )
    return pd.read_parquet(path)


def load_smangrul(raw_dir: Path = RAW_DIR, observed: date | None = None) -> list[Creative]:
    """Parse the packed instruction string, keep skincare rows."""
    df = _load_parquet(raw_dir / "ad-copy-generation.parquet")
    observed = observed or date.today()
    out: list[Creative] = []
    for i, content in enumerate(df["content"]):
        match = _SMANGRUL_RE.search(str(content))
        if not match:
            continue  # malformed row; skipped rather than half-parsed
        product = match.group("product").strip()
        description = match.group("description").strip()
        ad = match.group("ad").strip()
        if not is_skincare(product, description, ad):
            continue
        out.append(
            Creative(
                creative_id=f"t2_smangrul_{i:04d}",
                source_type="tier2",
                advertiser="synthetic (no advertiser)",
                platform="unknown",
                category="skincare",
                headline=product or None,
                body_copy=ad or None,
                source_url=None,
                date_observed=observed,
                rights_note=_RIGHTS["ad-copy-generation"],
            )
        )
    return out


def load_jaykin(raw_dir: Path = RAW_DIR, observed: date | None = None) -> list[Creative]:
    """Columnar source: product / description / ad (plus an empty artifact column)."""
    df = _load_parquet(raw_dir / "advertisement-copy.parquet")
    observed = observed or date.today()
    out: list[Creative] = []
    for i, row in df.iterrows():
        product = str(row.get("product") or "").strip()
        description = str(row.get("description") or "").strip()
        ad = str(row.get("ad") or "").strip()
        if not is_skincare(product, description, ad):
            continue
        out.append(
            Creative(
                creative_id=f"t2_jaykin_{i:04d}",
                source_type="tier2",
                advertiser="synthetic (no advertiser)",
                platform="unknown",
                category="skincare",
                headline=product or None,
                body_copy=ad or None,
                source_url=None,
                date_observed=observed,
                rights_note=_RIGHTS["advertisement-copy"],
            )
        )
    return out


def load_tier2(raw_dir: Path = RAW_DIR, observed: date | None = None) -> list[Creative]:
    """Both datasets, skincare-filtered and cross-deduplicated."""
    return dedupe(load_smangrul(raw_dir, observed) + load_jaykin(raw_dir, observed))
