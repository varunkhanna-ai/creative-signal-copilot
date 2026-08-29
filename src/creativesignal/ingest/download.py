"""W0.4: snapshot the Tier-1/Tier-2 Hugging Face datasets to `data/raw/`.

Downloads only. Normalization into the `creatives` table is W1.4
(`load_tier*.py`). `data/raw/` is gitignored — this script is how a grader
reproduces the corpus, so it must stay runnable end to end.

Licenses are recorded in `docs/data-governance.md`, read from each dataset
card at download time rather than assumed (implementation.md §0.1).
"""

from __future__ import annotations

from pathlib import Path

RAW_DIR = Path("data/raw")

TIER1_REPO = "PeterBrendan/AdImageNet"
TIER2_REPOS = ("smangrul/ad-copy-generation", "jaykin01/advertisement-copy")


def _out_path(repo: str, tier_dir: str) -> Path:
    """`smangrul/ad-copy-generation` -> data/raw/<tier_dir>/ad-copy-generation.parquet"""
    return RAW_DIR / tier_dir / f"{repo.split('/')[-1]}.parquet"


def download_tier1(raw_dir: Path = RAW_DIR) -> Path | None:
    """Snapshot AdImageNet. Returns None if the HF gate blocks access.

    The dataset went gated after the plan was written (decision-log B4). It is
    off the critical path — image corpus, no ad copy — so a gate is a warning,
    not a failure.
    """
    from datasets import load_dataset

    out = _out_path(TIER1_REPO, "tier1_adimagenet")
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        ds = load_dataset(TIER1_REPO, split="train")
    except Exception as exc:  # gated, or offline
        print(
            f"  SKIP {TIER1_REPO}: {type(exc).__name__}. "
            "Gated dataset — accept the terms on the HF page and run "
            "`huggingface-cli login`. See docs/decision-log.md B4."
        )
        return None
    ds.to_parquet(out)
    print(f"  {TIER1_REPO}: {len(ds)} rows -> {out}")
    return out


def download_tier2(raw_dir: Path = RAW_DIR) -> list[Path]:
    """Snapshot both ad-copy datasets in full; the skincare filter is W1.4's job."""
    from datasets import load_dataset

    written: list[Path] = []
    for repo in TIER2_REPOS:
        out = _out_path(repo, "tier2_adcopy")
        out.parent.mkdir(parents=True, exist_ok=True)
        ds = load_dataset(repo, split="train")
        ds.to_parquet(out)
        print(f"  {repo}: {len(ds)} rows -> {out}")
        written.append(out)
    return written


def main() -> None:
    print("Tier-1:")
    download_tier1()
    print("Tier-2:")
    download_tier2()
    print(
        "\nTier-3 is hand-curated, not downloaded: data/raw/tier3_meta_sample.csv "
        "(W0.3, Human). See docs/decision-log.md B1."
    )


if __name__ == "__main__":
    main()
