"""W2.2/W2.4/W2.5: cards, index ids, filter parsing, fusion arithmetic.

The fusion tests use `normalize` and hand-built score dicts rather than a
live index — the merge rule is the judgment-bearing part (Entry #10) and
should be verifiable without embedding anything.
"""

from __future__ import annotations

from datetime import date

import pytest

from creativesignal.retrieval.cards import build_card, build_card_text
from creativesignal.retrieval.index import document_id, parse_document_id
from creativesignal.retrieval.hybrid import normalize, parse_filters
from creativesignal.schema import Creative


def _creative(**overrides) -> Creative:
    fields = dict(
        creative_id="t3_001",
        source_type="tier3",
        advertiser="CeraVe",
        platform="facebook",
        category="moisturizer",
        headline="Dermatologist Recommended Moisturizer",
        body_copy="Three ceramides restore your skin barrier.",
        date_observed=date(2026, 7, 26),
        rights_note="ad-library copy only",
    )
    fields.update(overrides)
    return Creative(**fields)


# --- creative card --------------------------------------------------------


def test_card_text_labels_every_field():
    text = build_card_text(_creative())
    assert "Advertiser: CeraVe" in text
    assert "Headline: Dermatologist Recommended Moisturizer" in text


def test_card_text_omits_empty_fields_rather_than_writing_none():
    """"None" would become a high-frequency token across the whole index."""
    text = build_card_text(_creative(headline=None, body_copy=None))
    assert "None" not in text
    assert "Headline" not in text


def test_card_text_names_the_proxy_bucket_as_a_proxy():
    """Even the index text must not imply a performance tier."""
    text = build_card_text(_creative(proxy_bucket="high"))
    assert "not performance" in text


def test_card_carries_provenance_for_display():
    card = build_card(_creative(), summary="An authority-led moisturizer ad.")
    assert card.analyst_summary == "An authority-led moisturizer ad."
    assert "CeraVe" in card.provenance_line()
    assert "2026-07-26" in card.provenance_line()


def test_card_survives_a_missing_summary():
    """Cards alone are a working index — summaries are additive."""
    assert build_card(_creative()).analyst_summary is None


def test_card_picks_up_annotation_labels():
    card = build_card(_creative(), annotation={"hook_type": "authority_expert",
                                               "tone": "clinical"})
    assert (card.hook_type, card.tone) == ("authority_expert", "clinical")


# --- document ids ---------------------------------------------------------


def test_document_id_round_trips():
    doc_id = document_id("t2_smangrul_0146", "summary")
    assert parse_document_id(doc_id) == ("t2_smangrul_0146", "summary")


def test_document_id_round_trips_with_colons_in_the_creative_id():
    """rpartition, not split — an id containing '::' must still resolve."""
    assert parse_document_id(document_id("odd::id", "card")) == ("odd::id", "card")


# --- filter parsing -------------------------------------------------------


@pytest.mark.parametrize(
    "query,expected",
    [
        ("offer-led ads on instagram", {"platform": "instagram"}),
        ("meta ads about serum", {"platform": "facebook"}),
        ("tier 3 skincare examples", {"source_type": "tier3"}),
        ("long-running moisturizer ads", {"proxy_bucket": "high"}),
    ],
)
def test_parse_filters_extracts_known_terms(query, expected):
    assert parse_filters(query).as_dict() == expected


def test_parse_filters_returns_nothing_for_plain_queries():
    """Unrecognized text stays part of the free-text query."""
    assert parse_filters("hydrating serum for sensitive skin").as_dict() == {}


def test_parse_filters_combines_multiple_terms():
    parsed = parse_filters("tier 3 long-running ads on tiktok").as_dict()
    assert parsed == {
        "platform": "tiktok", "source_type": "tier3", "proxy_bucket": "high"
    }


# --- score fusion (Entry #10) --------------------------------------------


def test_normalize_maps_to_unit_range():
    assert normalize({"a": 2.0, "b": 4.0, "c": 6.0}) == {"a": 0.0, "b": 0.5, "c": 1.0}


def test_normalize_maps_equal_scores_to_one_not_zero():
    """If everything matched equally, all are good matches — not all bad.

    Mapping to 0.0 would let the other retriever silently decide the ranking.
    """
    assert normalize({"a": 3.0, "b": 3.0}) == {"a": 1.0, "b": 1.0}


def test_normalize_handles_a_single_result():
    assert normalize({"a": 7.5}) == {"a": 1.0}


def test_normalize_of_nothing_is_nothing():
    assert normalize({}) == {}
