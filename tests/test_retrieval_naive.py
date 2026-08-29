"""W1.11/W1.12: naive BM25 search, source interface, slice parsing.

Retrieval must work with no API key at all (§7) — none of these tests touch
the LLM, which is itself part of what they assert.
"""

from __future__ import annotations

from datetime import date

import pytest

from creativesignal.ingest.build_corpus import build_corpus, insert_creatives
from creativesignal.schema import Creative
from creativesignal.slice import format_evidence, parse_concepts
from creativesignal.sources.base import SearchFilters, SearchResult
from creativesignal.sources.curated import CuratedCorpusConnector, tokenize
from creativesignal.sources.live_stubs import MetaLiveConnector, TikTokConnector


@pytest.fixture
def corpus(tmp_path):
    db = tmp_path / "corpus.sqlite"
    build_corpus(db)
    insert_creatives(
        [
            Creative(
                creative_id="t2_serum",
                source_type="tier2",
                advertiser="synthetic (no advertiser)",
                platform="unknown",
                category="skincare",
                headline="Anti-Aging Serum",
                body_copy="Reduce fine lines and wrinkles with our hydrating serum.",
                date_observed=date(2026, 8, 28),
                rights_note="local use only",
            ),
            Creative(
                creative_id="t2_sunscreen",
                source_type="tier2",
                advertiser="synthetic (no advertiser)",
                platform="unknown",
                category="skincare",
                headline="Sunscreen",
                body_copy="Broad spectrum SPF 50 sun protection for every day.",
                date_observed=date(2026, 8, 28),
                rights_note="local use only",
            ),
            Creative(
                creative_id="t3_real",
                source_type="tier3",
                advertiser="CeraVe",
                platform="facebook",
                category="moisturizer",
                headline="Dermatologist Recommended Moisturizer",
                body_copy="Three ceramides restore your skin barrier.",
                source_url="https://example.com/ad/1",
                date_observed=date(2026, 7, 26),
                rights_note="ad-library copy only",
                proxy_bucket="high",
            ),
        ],
        db,
    )
    return CuratedCorpusConnector(db)


# --- tokenizer ------------------------------------------------------------


def test_tokenizer_lowercases_and_strips_punctuation():
    assert tokenize("SPF 50: broad-spectrum!") == ["spf", "50", "broad", "spectrum"]


def test_tokenizer_handles_empty_input():
    assert tokenize("") == []


# --- search ---------------------------------------------------------------


def test_search_ranks_term_overlap_first(corpus):
    results = corpus.search("hydrating serum for wrinkles")
    assert results[0].creative_id == "t2_serum"
    assert results[0].retrieved_by == "bm25"


def test_search_returns_nothing_without_term_overlap(corpus):
    """No shared terms is "no match"."""
    assert corpus.search("cryptocurrency trading platform") == []


def test_matches_survive_negative_bm25_scores(tmp_path):
    """Regression (Entry #16): BM25 IDF goes negative on common terms.

    When every document contains the query terms, BM25Okapi scores them all
    below zero. Filtering on `score > 0` dropped genuine matches entirely —
    on a small corpus this silently returned nothing.
    """
    db = tmp_path / "corpus.sqlite"
    build_corpus(db)
    insert_creatives(
        [
            Creative(
                creative_id=f"c{i}",
                source_type="tier2",
                advertiser="synthetic (no advertiser)",
                platform="unknown",
                category="skincare",
                headline=f"Gentle Cleanser {i}",
                body_copy="A gentle daily cleanser for sensitive skin.",
                date_observed=date(2026, 8, 28),
                rights_note="local use only",
            )
            for i in range(5)
        ],
        db,
    )
    results = CuratedCorpusConnector(db).search("gentle cleanser", limit=5)
    assert len(results) == 5, "identical docs all match; none should be dropped"
    assert all(r.score < 0 for r in results), "precondition: scores are negative here"


def test_search_respects_the_limit(corpus):
    assert len(corpus.search("skin", limit=1)) <= 1


def test_empty_query_returns_nothing(corpus):
    assert corpus.search("") == []


def test_filters_are_a_hard_prefilter(corpus):
    """BM25 scores are corpus-relative, so filtering must precede scoring."""
    results = corpus.search("skin", filters=SearchFilters(source_type="tier3"))
    assert {r.creative_id for r in results} <= {"t3_real"}


def test_filter_on_a_field_with_no_matches_returns_empty(corpus):
    assert corpus.search("serum", filters=SearchFilters(platform="tiktok")) == []


# --- record access --------------------------------------------------------


def test_get_returns_a_validated_creative(corpus):
    creative = corpus.get("t3_real")
    assert creative.advertiser == "CeraVe"
    assert creative.proxy_bucket == "high"


def test_get_unknown_id_returns_none(corpus):
    assert corpus.get("does_not_exist") is None


def test_all_creatives_filters_by_tier(corpus):
    assert len(corpus.all_creatives(SearchFilters(source_type="tier2"))) == 2
    assert len(corpus.all_creatives()) == 3


def test_missing_database_is_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="make ingest"):
        CuratedCorpusConnector(tmp_path / "nope.sqlite").all_creatives()


# --- live stubs stay unimplemented ---------------------------------------


@pytest.mark.parametrize("connector", [MetaLiveConnector(), TikTokConnector()])
def test_live_connectors_refuse_every_method(connector):
    """Not an unfinished task — a governance constraint asserted in code."""
    for call in (
        lambda: connector.search("serum"),
        lambda: connector.get("x"),
        lambda: connector.all_creatives(),
    ):
        with pytest.raises(NotImplementedError, match="never implemented"):
            call()


# --- slice helpers --------------------------------------------------------


def test_evidence_block_attaches_ids_to_their_text(corpus):
    results = corpus.search("serum")
    rendered = format_evidence(results)
    assert "[t2_serum]" in rendered
    assert "Anti-Aging Serum" in rendered


def test_parse_concepts_keeps_cited_and_drops_uncited():
    """An uncited concept is dropped, not shown with a caveat."""
    concepts = parse_concepts(
        '[{"title": "Cited", "headline": "h", "body_copy": "b", '
        '"cited_creative_ids": ["t2_serum"]}, '
        '{"title": "Uncited", "headline": "h", "body_copy": "b", '
        '"cited_creative_ids": []}]'
    )
    assert [c.title for c in concepts] == ["Cited"]


def test_parse_concepts_survives_a_code_fence():
    concepts = parse_concepts(
        '```json\n[{"title": "T", "headline": "h", "body_copy": "b", '
        '"cited_creative_ids": ["x"]}]\n```'
    )
    assert len(concepts) == 1


def test_parse_concepts_survives_garbage():
    assert parse_concepts("Sorry, I can't do that.") == []


def test_parse_concepts_skips_malformed_entries_without_losing_good_ones():
    concepts = parse_concepts(
        '[{"nope": 1}, {"title": "Good", "headline": "h", "body_copy": "b", '
        '"cited_creative_ids": ["x"]}]'
    )
    assert [c.title for c in concepts] == ["Good"]


def test_platform_filter_matches_within_a_placement_list(tmp_path):
    """Regression (Entry #28): `platform` is a comma-separated Ad Library
    placement list, so equality never matched a single platform name —
    filtering on "facebook" silently returned nothing."""
    db = tmp_path / "corpus.sqlite"
    build_corpus(db)
    insert_creatives(
        [
            Creative(
                creative_id="t3_multi",
                source_type="tier3",
                advertiser="CeraVe",
                platform="FACEBOOK,INSTAGRAM,MESSENGER",
                category="moisturizer",
                headline="Daily moisturizer",
                body_copy="Ceramides restore your skin barrier.",
                date_observed=date(2026, 7, 26),
                rights_note="ad-library copy only",
            )
        ],
        db,
    )
    source = CuratedCorpusConnector(db)
    for name in ("facebook", "FACEBOOK", "instagram", "messenger"):
        assert len(source.all_creatives(SearchFilters(platform=name))) == 1, name
    assert source.all_creatives(SearchFilters(platform="tiktok")) == []


def test_platform_filter_does_not_match_a_partial_token(tmp_path):
    """"face" must not match "FACEBOOK" — comma boundaries, not substrings."""
    db = tmp_path / "corpus.sqlite"
    build_corpus(db)
    insert_creatives(
        [
            Creative(
                creative_id="t3_x", source_type="tier3", advertiser="A",
                platform="FACEBOOK,INSTAGRAM", category="serum",
                headline="h", body_copy="b", date_observed=date(2026, 7, 26),
                rights_note="n",
            )
        ],
        db,
    )
    assert CuratedCorpusConnector(db).all_creatives(SearchFilters(platform="face")) == []
