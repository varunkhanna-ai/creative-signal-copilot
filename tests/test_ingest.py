"""W1.4 smoke tests: loaders normalize to `Creative`, corpus round-trips.

The Tier-3 tests run against a synthetic fixture CSV, not real curated data
(decision-log B1). They prove the loader's contract — required columns,
derived proxy fields, provenance preserved — so that dropping the real
`data/raw/tier3_meta_sample.csv` in place needs no code change.
"""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from creativesignal.ingest.build_corpus import (
    build_corpus,
    count_by_tier,
    insert_creatives,
)
from creativesignal.ingest.load_tier2 import dedupe, is_skincare
from creativesignal.ingest.load_tier3 import (
    compute_days_active,
    compute_proxy_bucket,
    load_tier3,
)
from creativesignal.schema import Creative

TIER3_HEADER = (
    "creative_id,advertiser,ad_library_url,platform,category,headline,body_copy,"
    "start_date,date_observed,days_active,variant_count,source_type,rights_note,notes\n"
)


def _tier3_csv(tmp_path, rows: str):
    path = tmp_path / "tier3_meta_sample.csv"
    path.write_text(TIER3_HEADER + rows)
    return path


# --- Tier-2 filter -------------------------------------------------------


def test_skincare_filter_matches_on_any_field():
    assert is_skincare("Retinol Serum", None, None)
    assert is_skincare("Daily wash", "a gentle cleanser for daily use", None)
    assert not is_skincare("Harem pants", "bohemian trousers", "shop now")


def test_skincare_filter_is_case_insensitive():
    assert is_skincare("HYALURONIC ACID")


@pytest.mark.parametrize(
    "product,body",
    [
        # "wrinkle" here means creased shirts, not skin.
        ("Steam Iron", "Experience wrinkle-free clothing with ease."),
        ("Garment Steamer", "Experience wrinkle removal and garment care."),
        # "serum" here is haircare.
        ("Hair Serum", "Shiny, manageable, frizz-free locks."),
    ],
)
def test_skincare_filter_vetoes_non_skincare_products(product, body):
    """Regression: these three matched on body-copy keyword overlap alone."""
    assert not is_skincare(product, body)


def test_dedupe_drops_identical_ad_copy():
    """The two Tier-2 datasets share most rows verbatim."""
    a = _creative("t2_smangrul_0343", body_copy="Look sharp with the Iron!")
    b = _creative("t2_jaykin_0312", body_copy="Look sharp with the Iron!")
    c = _creative("t2_jaykin_0396", body_copy="Achieve a natural look with CC Cream!")
    kept = dedupe([a, b, c])
    assert [x.creative_id for x in kept] == ["t2_smangrul_0343", "t2_jaykin_0396"]


def test_dedupe_ignores_whitespace_and_case():
    a = _creative("a", body_copy="Glow  serum\nfor you")
    b = _creative("b", body_copy="glow serum for you")
    assert len(dedupe([a, b])) == 1


def test_dedupe_drops_rows_with_no_copy():
    """A creative with no ad copy has nothing to retrieve on."""
    assert dedupe([_creative("a", body_copy=None)]) == []


# --- Tier-3 derived proxy fields (F1) ------------------------------------


def test_days_active_from_start_and_observed():
    assert compute_days_active(date(2026, 5, 1), date(2026, 7, 26)) == 86


def test_days_active_never_negative():
    # A start date after the observation date is a curation error, not a
    # negative duration.
    assert compute_days_active(date(2026, 8, 1), date(2026, 7, 1)) == 0


def test_days_active_none_without_start():
    assert compute_days_active(None, date(2026, 7, 1)) is None


@pytest.mark.parametrize(
    "days,variants,expected",
    [
        (120, 1, "high"),   # long-running alone qualifies
        (10, 8, "high"),    # heavy variation alone qualifies
        (60, 2, "mid"),
        (10, 1, "low"),
        (29, 0, "low"),
        (30, 0, "mid"),     # boundary: LOW_DAYS is exclusive
    ],
)
def test_proxy_bucket_thresholds(days, variants, expected):
    assert compute_proxy_bucket(days, variants) == expected


def test_proxy_bucket_none_when_no_signal():
    assert compute_proxy_bucket(None, None) is None


# --- Tier-3 loader contract ----------------------------------------------


def test_tier3_missing_file_returns_empty(tmp_path):
    """B1: absent curated file must skip cleanly, not crash the ingest path."""
    assert load_tier3(tmp_path / "nope.csv") == []


def test_tier3_loads_and_derives(tmp_path):
    path = _tier3_csv(
        tmp_path,
        "T3-001,CeraVe,https://example.com/ad/1,facebook,moisturizer,"
        "Daily Moisturizer,Three ceramides restore your skin barrier.,"
        "2026-05-01,2026-07-26,86,3,meta_ad_library,Public ad copy only,\n",
    )
    [creative] = load_tier3(path)
    assert creative.creative_id == "T3-001"
    assert creative.source_type == "tier3"
    assert creative.advertiser == "CeraVe"
    assert creative.source_url == "https://example.com/ad/1"
    # Derived, not trusted from the sheet.
    assert creative.days_active == 86
    assert creative.proxy_bucket == "mid"


def test_tier3_recomputes_rather_than_trusting_sheet(tmp_path):
    """The sheet's days_active is wrong; start/observed are authoritative."""
    path = _tier3_csv(
        tmp_path,
        "T3-002,Acme,https://example.com/ad/2,facebook,serum,H,B,"
        "2026-01-01,2026-07-01,9999,1,meta_ad_library,note,\n",
    )
    [creative] = load_tier3(path)
    assert creative.days_active == 181
    assert creative.proxy_bucket == "high"


def test_tier3_blank_rights_note_is_flagged_not_dropped(tmp_path):
    """W0.3 left some rights_note/category cells blank — surface, don't drop."""
    path = _tier3_csv(
        tmp_path,
        "T3-003,Acme,https://example.com/ad/3,facebook,,H,B,"
        "2026-01-01,2026-07-01,181,1,meta_ad_library,,\n",
    )
    [creative] = load_tier3(path)
    assert "MISSING" in creative.rights_note
    assert creative.category == "skincare (uncategorized)"


def test_tier3_rejects_wrong_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("creative_id,advertiser\nT3-001,Acme\n")
    with pytest.raises(ValueError, match="missing required column"):
        load_tier3(path)


# --- Corpus write path ---------------------------------------------------


def _creative(creative_id: str, **overrides) -> Creative:
    fields = dict(
        creative_id=creative_id,
        source_type="tier2",
        advertiser="synthetic (no advertiser)",
        platform="unknown",
        category="skincare",
        headline="Glow serum",
        body_copy="Brightening vitamin C serum.",
        date_observed=date(2026, 8, 28),
        rights_note="local use only",
    )
    fields.update(overrides)
    return Creative(**fields)


def test_insert_and_count_by_tier(tmp_path):
    db = tmp_path / "corpus.sqlite"
    build_corpus(db)
    written = insert_creatives(
        [_creative("a"), _creative("b"), _creative("c", source_type="tier3")], db
    )
    assert written == 3
    assert count_by_tier(db) == {"tier2": 2, "tier3": 1}


def test_insert_is_idempotent(tmp_path):
    """`make ingest` must be safe to re-run without duplicating rows."""
    db = tmp_path / "corpus.sqlite"
    build_corpus(db)
    insert_creatives([_creative("a")], db)
    insert_creatives([_creative("a", headline="Updated headline")], db)
    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT creative_id, headline FROM creatives").fetchall()
    assert rows == [("a", "Updated headline")]


def test_creative_survives_db_round_trip(tmp_path):
    """Dates go to SQLite as ISO strings and must come back as a valid model."""
    db = tmp_path / "corpus.sqlite"
    build_corpus(db)
    original = _creative(
        "t3_x",
        source_type="tier3",
        start_date=date(2026, 5, 1),
        days_active=86,
        variant_count=3,
        proxy_bucket="mid",
    )
    insert_creatives([original], db)
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute("SELECT * FROM creatives").fetchone())
    assert Creative.model_validate(row) == original
