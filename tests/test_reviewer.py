"""W4.9: the planted-violation test. This is the demo beat, asserted.

A concept containing a prohibited claim MUST be flagged. Everything else in
the reviewer is testable because the checks are deterministic — no API key,
same verdict every run (Entry #15).
"""

from __future__ import annotations

import pytest

from creativesignal.agents.reviewer import (
    SIMILARITY_THRESHOLD,
    check_false_scarcity,
    check_prohibited_targeting,
    check_similarity,
    check_unsupported_claims,
    evidence_map,
    jaccard,
    review_concept,
)
from creativesignal.schema import Concept


def _concept(headline="Glow serum", body="Brightening vitamin C serum.", **kw):
    fields = dict(
        title=kw.pop("title", "Test concept"),
        headline=headline,
        body_copy=body,
        cited_creative_ids=kw.pop("cited_creative_ids", ["c1"]),
    )
    fields.update(kw)
    return Concept(**fields)


# --- THE PLANTED VIOLATION (W4.9) ----------------------------------------


def test_planted_prohibited_claim_is_flagged():
    """The demo beat: an invented efficacy claim must not pass review."""
    concept = _concept(
        headline="Clinically proven to reverse wrinkles",
        body="Our FDA-approved formula cures aging skin permanently.",
    )
    evidence = {"c1": "A gentle daily moisturizer for soft skin."}

    result = review_concept(concept, evidence)

    assert not result.passed, "a planted efficacy claim must fail review"
    claims = result.flags_for("unsupported_claim")
    assert claims, "expected at least one unsupported_claim flag"
    flagged = {f.span.lower() for f in claims if f.span}
    assert "clinically proven" in flagged
    assert any("fda" in s for s in flagged)
    # Every flag must justify itself on expand.
    assert all(f.evidence.strip() for f in claims)


def test_claim_supported_by_cited_evidence_is_not_flagged():
    """The reviewer checks traceability, not truth."""
    concept = _concept(
        headline="Dermatologist recommended daily moisturizer",
        body="A gentle formula for everyday use.",
    )
    evidence = {"c1": "Dermatologist recommended daily moisturizer with ceramides."}
    assert check_unsupported_claims(concept, evidence) == []


def test_same_claim_is_flagged_when_the_cited_ad_does_not_make_it():
    concept = _concept(headline="Dermatologist recommended moisturizer")
    evidence = {"c1": "A hydrating cream for dry skin."}
    flags = check_unsupported_claims(concept, evidence)
    assert len(flags) == 1
    assert flags[0].severity == "claim"


def test_quantified_outcome_claim_is_flagged():
    concept = _concept(body="Reduces wrinkles by 47% in 14 days.")
    assert check_unsupported_claims(concept, {"c1": "A moisturizer."})


def test_uncited_concept_is_flagged_even_when_clean():
    concept = _concept(
        headline="A nice serum", body="It is pleasant.", cited_creative_ids=[]
    )
    result = review_concept(concept, {})
    assert not result.passed
    assert "cites no evidence" in result.flags[0].message


# --- scarcity -------------------------------------------------------------


def test_false_scarcity_flagged_without_a_promotion_window():
    concept = _concept(body="Limited stock - act now!")
    flags = check_false_scarcity(concept, has_promotion=False)
    assert {f.span.lower() for f in flags} >= {"limited stock", "act now"}


def test_scarcity_not_flagged_when_a_real_promotion_exists():
    concept = _concept(body="Limited stock during our July sale.")
    assert check_false_scarcity(concept, has_promotion=True) == []


def test_scarcity_flag_names_the_corpus_artifact():
    """Every corpus ad says 'Limited stock' — the flag must say why (B2)."""
    [flag] = check_false_scarcity(_concept(body="Limited stock!"))
    assert "corpus" in flag.evidence.lower()


# --- targeting ------------------------------------------------------------


def test_prohibited_targeting_flagged():
    concept = _concept(body="Fix your face before it's too late.")
    flags = check_prohibited_targeting(concept)
    assert flags and flags[0].severity == "claim"


def test_ordinary_skincare_copy_is_not_flagged_as_targeting():
    """Over-flagging normal vocabulary would make the reviewer noise."""
    concept = _concept(body="A gentle cleanser for sensitive skin.")
    assert check_prohibited_targeting(concept) == []


# --- similarity -----------------------------------------------------------


def test_jaccard_is_one_for_identical_text():
    assert jaccard("gentle cleanser daily", "gentle cleanser daily") == 1.0


def test_jaccard_is_zero_for_disjoint_text():
    assert jaccard("gentle cleanser", "cryptocurrency trading") == 0.0


def test_near_copy_of_a_retrieved_ad_is_flagged():
    ad = "Reveal your natural beauty with Facial Cleanser. Experience a fresh and radiant complexion."
    concept = _concept(headline="Reveal your natural beauty", body=ad)
    flags = check_similarity(concept, {"c1": ad})
    assert flags
    assert flags[0].severity == "similarity"
    assert flags[0].related_creative_ids == ["c1"]


def test_similarity_flag_shows_the_overlapping_terms_as_evidence():
    ad = "Reveal your natural beauty with Facial Cleanser for a radiant complexion."
    [flag] = check_similarity(_concept(headline="x", body=ad), {"c1": ad})
    assert "Shared terms" in flag.evidence


def test_distinct_concept_is_not_flagged_for_similarity():
    concept = _concept(headline="Barrier repair", body="Ceramides for overnight recovery.")
    evidence = {"c1": "Limited stock sunscreen with broad spectrum SPF 50 protection."}
    assert check_similarity(concept, evidence) == []


def test_similarity_is_checked_against_all_retrieved_not_only_cited():
    """The generator could have drawn on anything it saw."""
    ad = "Exfoliate for a fresh look with Face Scrub for a clear radiant complexion."
    concept = _concept(headline="Exfoliate for a fresh look", body=ad,
                       cited_creative_ids=["c1"])
    flags = check_similarity(concept, {"c2": ad})  # c2 was retrieved, not cited
    assert flags and flags[0].related_creative_ids == ["c2"]


def test_similarity_does_not_block_passing():
    """Amber is advisory — only claim-severity flags fail a concept."""
    ad = "Reveal your natural beauty with Facial Cleanser for a radiant complexion today."
    concept = _concept(headline="Reveal your natural beauty", body=ad,
                       cited_creative_ids=["c1"])
    result = review_concept(concept, {"c1": ad}, has_promotion=True)
    assert result.flags_for("similarity")
    assert result.passed


# --- result shape ---------------------------------------------------------


def test_clean_concept_passes_with_all_checks_recorded():
    concept = _concept(
        headline="Barrier repair overnight",
        body="Ceramides support your skin barrier while you sleep.",
    )
    result = review_concept(concept, {"c1": "A sunscreen with SPF 50."})
    assert result.passed
    assert set(result.checks_run) == {
        "unsupported_claim", "false_scarcity", "prohibited_targeting", "similarity"
    }


def test_every_flag_carries_evidence():
    """A flag that can't justify itself on expand is an unexplainable judgment."""
    concept = _concept(
        headline="Clinically proven cure",
        body="Limited stock. Fix your face before it's too late.",
    )
    result = review_concept(concept, {"c1": "A moisturizer."})
    assert len(result.flags) >= 3
    assert all(f.evidence.strip() for f in result.flags)


def test_evidence_map_builds_id_to_copy():
    class _C:
        creative_id, headline, body_copy = "c1", "Head", "Body"

    assert evidence_map([_C()]) == {"c1": "Head Body"}


@pytest.mark.parametrize("threshold", [0.3, 0.9])
def test_similarity_threshold_is_configurable(threshold):
    ad = "gentle daily cleanser for sensitive skin with a fresh clean finish"
    flags = check_similarity(_concept(headline="x", body=ad), {"c1": ad}, threshold)
    assert flags  # identical text exceeds any threshold <= 1.0
