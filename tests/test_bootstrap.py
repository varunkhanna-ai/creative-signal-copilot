"""W1.6 tests: prompt rendering, response parsing, verification-sheet round trip.

No live LLM call — `label_rows` is the only function that calls out, and it is
a thin loop over `complete()` + `parse_response()`, both covered here.
"""

from __future__ import annotations

import csv

import pytest

from creativesignal.annotate.bootstrap import (
    SeedLabel,
    build_prompt,
    load_corrected_seed,
    parse_response,
    verification_accuracy,
    write_seed_labels,
    write_verification_sheet,
)
from creativesignal.annotate.taxonomy import HOOK_TYPES, TONE_LABELS, UNCLEAR_LABEL


def _label(creative_id: str, hook: str = "benefit_promise", tone: str = "aspirational"):
    return SeedLabel(
        creative_id=creative_id,
        headline="Glow Serum",
        body_copy="Radiant skin in two weeks.",
        hook_type=hook,
        tone=tone,
        hook_reason="opens on end state",
        tone_reason="idealized self",
    )


# --- prompt ---------------------------------------------------------------


def test_prompt_inlines_every_frozen_label():
    """The model must see exactly the labels the validator will accept."""
    prompt = build_prompt("Glow Serum", "Radiant skin in two weeks.")
    for label in (*HOOK_TYPES, *TONE_LABELS):
        assert label in prompt


def test_prompt_includes_the_ad_text():
    prompt = build_prompt("Glow Serum", "Radiant skin.")
    assert "Glow Serum" in prompt
    assert "Radiant skin." in prompt


def test_prompt_handles_missing_fields():
    assert "(none)" in build_prompt("", "")


# --- response parsing -----------------------------------------------------


def test_parses_clean_json():
    hook, tone, hook_reason, _ = parse_response(
        '{"hook_type": "offer_led", "tone": "urgent", '
        '"hook_reason": "leads with discount", "tone_reason": "act now"}'
    )
    assert (hook, tone) == ("offer_led", "urgent")
    assert hook_reason == "leads with discount"


def test_parses_json_wrapped_in_a_code_fence():
    hook, tone, _, _ = parse_response(
        '```json\n{"hook_type": "social_proof", "tone": "playful"}\n```'
    )
    assert (hook, tone) == ("social_proof", "playful")


def test_off_taxonomy_label_becomes_unclear_not_an_exception():
    """One bad row must not abort a 250-row batch."""
    hook, tone, _, _ = parse_response(
        '{"hook_type": "storytelling", "tone": "sassy"}'
    )
    assert hook == UNCLEAR_LABEL
    assert tone == UNCLEAR_LABEL


def test_cross_axis_label_becomes_unclear():
    hook, _, _, _ = parse_response('{"hook_type": "clinical", "tone": "clinical"}')
    assert hook == UNCLEAR_LABEL


def test_unparseable_response_is_survivable():
    hook, tone, reason, _ = parse_response("I'm sorry, I can't help with that.")
    assert hook == tone == UNCLEAR_LABEL
    assert "unparseable" in reason


def test_explicit_unclear_is_preserved():
    hook, tone, _, _ = parse_response(
        '{"hook_type": "unclear", "tone": "clinical"}'
    )
    assert hook == UNCLEAR_LABEL
    assert tone == "clinical"


# --- verification sheet ---------------------------------------------------


def test_verification_sheet_has_blank_correction_columns(tmp_path):
    sheet = tmp_path / "verify.csv"
    write_verification_sheet([_label("a"), _label("b")], sheet, sample_size=2)
    rows = list(csv.DictReader(sheet.open(encoding="utf-8")))
    assert len(rows) == 2
    assert all(r["correct_hook_type"] == "" and r["correct_tone"] == "" for r in rows)


def test_verification_sample_is_reproducible(tmp_path):
    """A fixed seed means W1.7 verifies the same rows if the sheet is regenerated."""
    labels = [_label(f"c{i}") for i in range(20)]
    first, second = tmp_path / "a.csv", tmp_path / "b.csv"
    write_verification_sheet(labels, first, sample_size=5)
    write_verification_sheet(labels, second, sample_size=5)
    assert first.read_text() == second.read_text()


def test_corrections_override_model_labels(tmp_path):
    labels_path = tmp_path / "seed.csv"
    sheet = tmp_path / "verify.csv"
    write_seed_labels([_label("a"), _label("b")], labels_path)
    write_verification_sheet([_label("a"), _label("b")], sheet, sample_size=2)

    rows = list(csv.DictReader(sheet.open(encoding="utf-8")))
    rows[0]["correct_hook_type"] = "social_proof"  # human disagrees
    with sheet.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    corrected = {s.creative_id: s for s in load_corrected_seed(sheet, labels_path)}
    assert corrected[rows[0]["creative_id"]].hook_type == "social_proof"
    # Blank correction means "model was right" — unchanged.
    assert corrected[rows[1]["creative_id"]].hook_type == "benefit_promise"


def test_correction_to_an_invalid_label_is_rejected(tmp_path):
    """A typo in the human's sheet must fail loudly, not enter training."""
    labels_path = tmp_path / "seed.csv"
    sheet = tmp_path / "verify.csv"
    write_seed_labels([_label("a")], labels_path)
    write_verification_sheet([_label("a")], sheet, sample_size=1)
    rows = list(csv.DictReader(sheet.open(encoding="utf-8")))
    rows[0]["correct_hook_type"] = "sociall_proof"
    with sheet.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="not a frozen hook_type"):
        load_corrected_seed(sheet, labels_path)


def test_verification_accuracy_counts_blank_as_correct(tmp_path):
    sheet = tmp_path / "verify.csv"
    write_verification_sheet([_label(f"c{i}") for i in range(4)], sheet, sample_size=4)
    rows = list(csv.DictReader(sheet.open(encoding="utf-8")))
    rows[0]["correct_hook_type"] = "social_proof"  # 1 of 4 wrong
    with sheet.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    stats = verification_accuracy(sheet)
    assert stats["n"] == 4
    assert stats["hook_accuracy"] == 0.75
    assert stats["tone_accuracy"] == 1.0
