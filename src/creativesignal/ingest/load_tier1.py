"""W1.4: Tier-1 (AdImageNet) -> normalized `Creative` records.

AdImageNet is an *image* corpus. The retrieval unit in this project is ad copy
(creative card + analyst summary, §8), so Tier-1 contributes breadth to the
corpus rather than anything the text index can rank — it is deliberately off
the critical path.

The dataset went gated on Hugging Face after the plan was written
(decision-log B4), so this loader currently returns an empty list. It is kept
whole rather than stubbed so that accepting the gate is the only step needed.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from creativesignal.schema import Creative

TIER1_PARQUET = Path("data/raw/tier1_adimagenet/AdImageNet.parquet")

_RIGHTS = (
    "PeterBrendan/AdImageNet, MIT license per the HF card. Gated dataset — "
    "access accepted per-account. See docs/data-governance.md."
)


def load_tier1(
    path: Path = TIER1_PARQUET, observed: date | None = None
) -> list[Creative]:
    """Load AdImageNet if the snapshot exists; otherwise skip with a message."""
    import pandas as pd

    if not path.exists():
        print(
            f"  Tier-1 not available: {path} missing. Skipping. "
            "Gated on Hugging Face — see docs/decision-log.md B4. Off the "
            "critical path (images, no ad copy)."
        )
        return []

    df = pd.read_parquet(path)
    observed = observed or date.today()
    text_col = next(
        (c for c in ("description", "text", "caption", "alt_text") if c in df.columns),
        None,
    )
    out: list[Creative] = []
    for i, row in df.iterrows():
        body = str(row[text_col]).strip() if text_col else ""
        out.append(
            Creative(
                creative_id=f"t1_adimagenet_{i:05d}",
                source_type="tier1",
                advertiser="unknown (image corpus)",
                platform="display",
                category="unclassified",
                headline=None,
                body_copy=body or None,
                source_url=None,
                date_observed=observed,
                rights_note=_RIGHTS,
            )
        )
    return out
