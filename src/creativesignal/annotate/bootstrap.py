"""W1.6 (F2): one-time LLM seed-labeling pass to bootstrap the annotator.

The circularity F2 names: the logistic regression needs labeled data, but
labels are what it produces. The break is a one-time pass — the LLM labels a
seed set against the frozen taxonomy, a human verifies a random 50 (W1.7),
and the LR trains on the corrected result. After that the runtime flow is
LR-first with LLM escalation only below threshold (W1.10).

This module writes two artifacts:
  - `data/seed_labels.csv`      — every labeled row, machine-readable
  - `data/seed_verification.csv` — a random 50-row sheet for W1.7, with blank
                                   correction columns for the human to fill

The verification sheet is a *separate file* on purpose: W1.7 edits it by hand
and `load_corrected_seed()` reads it back, so a re-run of the bootstrap never
overwrites human corrections.
"""

from __future__ import annotations

import csv
import json
import random
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from creativesignal.annotate.taxonomy import (
    HOOK_TYPE_DEFINITIONS,
    TONE_DEFINITIONS,
    UNCLEAR_LABEL,
    validate_hook_type,
    validate_tone,
)
from creativesignal.llm import HAIKU_MODEL, complete, load_prompt

DB_PATH = Path("data/corpus.sqlite")
SEED_LABELS = Path("data/seed_labels.csv")
VERIFICATION_SHEET = Path("data/seed_verification.csv")

PROMPT_NAME = "bootstrap_label_v1"
VERIFICATION_SAMPLE_SIZE = 50
SEED_TARGET = 250  # F2's "~250 Tier-2 rows"
RANDOM_SEED = 20260828  # fixed: the verification sample must be reproducible


@dataclass
class SeedLabel:
    creative_id: str
    headline: str
    body_copy: str
    hook_type: str
    tone: str
    hook_reason: str
    tone_reason: str


def _definitions_block(definitions: dict[str, str]) -> str:
    return "\n".join(f"- {label}: {text}" for label, text in definitions.items())


def build_prompt(headline: str, body_copy: str) -> str:
    """Render the versioned prompt with the frozen taxonomy inlined.

    Definitions come from `taxonomy.py` rather than being duplicated in the
    prompt file, so the labels the LLM sees can never drift from the labels
    the validator accepts.
    """
    return load_prompt(PROMPT_NAME).format(
        hook_definitions=_definitions_block(HOOK_TYPE_DEFINITIONS),
        tone_definitions=_definitions_block(TONE_DEFINITIONS),
        headline=headline or "(none)",
        body_copy=body_copy or "(none)",
    )


def parse_response(text: str) -> tuple[str, str, str, str]:
    """Parse the model's JSON reply, validating labels against the taxonomy.

    An off-taxonomy label is coerced to `unclear` rather than raising: one bad
    row should not abort a 250-row batch, and `unclear` is already the
    designed escape hatch, so the row stays visible and countable.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):  # strip a stray code fence
        cleaned = cleaned.split("```")[1].removeprefix("json").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return UNCLEAR_LABEL, UNCLEAR_LABEL, "unparseable response", ""

    def _safe(value: object, validator) -> str:
        try:
            return validator(str(value))
        except ValueError:
            return UNCLEAR_LABEL

    return (
        _safe(data.get("hook_type"), validate_hook_type),
        _safe(data.get("tone"), validate_tone),
        str(data.get("hook_reason", ""))[:120],
        str(data.get("tone_reason", ""))[:120],
    )


def fetch_rows(limit: int = SEED_TARGET, db_path: Path = DB_PATH) -> list[sqlite3.Row]:
    """Tier-2 rows with ad copy, which is what the bootstrap labels (F2)."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT creative_id, headline, body_copy FROM creatives "
            "WHERE source_type = 'tier2' AND body_copy IS NOT NULL "
            "ORDER BY creative_id LIMIT ?",
            (limit,),
        ).fetchall()


def label_rows(rows: list[sqlite3.Row]) -> list[SeedLabel]:
    """Label each row with the Haiku tier (high volume, cheap — §0.1)."""
    labeled: list[SeedLabel] = []
    for i, row in enumerate(rows, start=1):
        headline = row["headline"] or ""
        body = row["body_copy"] or ""
        response = complete(
            build_prompt(headline, body),
            task="bootstrap_label",
            model=HAIKU_MODEL,
            prompt_version=PROMPT_NAME,
            max_tokens=200,
        )
        hook, tone, hook_reason, tone_reason = parse_response(response.text)
        labeled.append(
            SeedLabel(row["creative_id"], headline, body, hook, tone, hook_reason, tone_reason)
        )
        if i % 25 == 0:
            print(f"  labeled {i}/{len(rows)}")
    return labeled


def write_seed_labels(labels: list[SeedLabel], path: Path = SEED_LABELS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(labels[0])) if labels else
                                ["creative_id", "headline", "body_copy", "hook_type",
                                 "tone", "hook_reason", "tone_reason"])
        writer.writeheader()
        writer.writerows(asdict(label) for label in labels)


def write_verification_sheet(
    labels: list[SeedLabel],
    path: Path = VERIFICATION_SHEET,
    sample_size: int = VERIFICATION_SAMPLE_SIZE,
) -> int:
    """Write the W1.7 human-verification sheet: random rows, blank corrections.

    `correct_hook_type` / `correct_tone` are left empty and mean "the model
    was right." The human fills a cell only to disagree, which keeps 50 rows
    of verification to roughly the 45 minutes F2 budgets.
    """
    rng = random.Random(RANDOM_SEED)
    sample = rng.sample(labels, min(sample_size, len(labels)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["creative_id", "headline", "body_copy", "llm_hook_type", "llm_tone",
             "hook_reason", "tone_reason", "correct_hook_type", "correct_tone", "notes"]
        )
        for label in sample:
            writer.writerow(
                [label.creative_id, label.headline, label.body_copy, label.hook_type,
                 label.tone, label.hook_reason, label.tone_reason, "", "", ""]
            )
    return len(sample)


def load_corrected_seed(
    verification_path: Path = VERIFICATION_SHEET,
    labels_path: Path = SEED_LABELS,
) -> list[SeedLabel]:
    """Read seed labels with W1.7 human corrections applied.

    This is what the LR trains on (W1.8) — never the raw LLM output, since
    the whole point of the verification pass is that a human overrides it.
    """
    if not labels_path.exists():
        raise FileNotFoundError(
            f"{labels_path} missing — run `make annotate` (W1.6) first."
        )
    with labels_path.open(encoding="utf-8") as handle:
        labels = {
            row["creative_id"]: SeedLabel(**row) for row in csv.DictReader(handle)
        }

    if verification_path.exists():
        with verification_path.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                label = labels.get(row["creative_id"])
                if label is None:
                    continue
                # A blank correction cell means "model was right".
                if row.get("correct_hook_type", "").strip():
                    label.hook_type = validate_hook_type(row["correct_hook_type"].strip())
                if row.get("correct_tone", "").strip():
                    label.tone = validate_tone(row["correct_tone"].strip())
    return list(labels.values())


def verification_accuracy(verification_path: Path = VERIFICATION_SHEET) -> dict[str, float]:
    """Annotator accuracy vs. the verified rows — W1's stated deliverable.

    The *measurement* is the deliverable, whatever the number turns out to be.
    """
    if not verification_path.exists():
        raise FileNotFoundError(f"{verification_path} missing — W1.7 not done.")
    with verification_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return {"n": 0, "hook_accuracy": 0.0, "tone_accuracy": 0.0}
    hook_ok = sum(1 for r in rows if not r.get("correct_hook_type", "").strip())
    tone_ok = sum(1 for r in rows if not r.get("correct_tone", "").strip())
    return {
        "n": float(len(rows)),
        "hook_accuracy": hook_ok / len(rows),
        "tone_accuracy": tone_ok / len(rows),
    }


def main() -> None:
    rows = fetch_rows()
    if not rows:
        print(
            "  No Tier-2 rows with copy found. Run `make download && make ingest` "
            "first. See docs/decision-log.md B2 — the corpus is currently 9 rows."
        )
        return
    print(f"Labeling {len(rows)} rows with {HAIKU_MODEL} ...")
    labels = label_rows(rows)
    write_seed_labels(labels)
    n = write_verification_sheet(labels)
    unclear = sum(1 for x in labels if x.hook_type == UNCLEAR_LABEL or x.tone == UNCLEAR_LABEL)
    print(f"\n  seed labels: {len(labels)} -> {SEED_LABELS}")
    print(f"  unclear on at least one axis: {unclear} ({unclear / len(labels):.0%})")
    print(f"  verification sheet: {n} rows -> {VERIFICATION_SHEET}")
    print("\nW1.7: fill correct_hook_type / correct_tone only where the model is wrong.")


if __name__ == "__main__":
    main()
