"""W3.6: tree features, refusal guards, and the honesty wording rule.

Trained against a synthetic frame — Tier-3 does not exist (B1), so the tree
has never seen real data. These tests pin the contract so that dropping real
data in needs no code change.
"""

from __future__ import annotations

import pytest

from creativesignal.insight.tree import (
    DISCLAIMER,
    rule_claim,
    BANNED_IN_RULES,
    MAX_DEPTH,
    InsufficientTreeData,
    TreeRule,
    build_features,
    rule_to_sentence,
    rules_as_sentences,
    train_tree,
)


def _rows(n: int = 60) -> list[dict]:
    """Synthetic Tier-3-shaped rows with a learnable signal."""
    rows = []
    for i in range(n):
        long_running = i % 2 == 0
        rows.append(
            {
                "creative_id": f"t3_{i:03d}",
                "headline": "Dermatologist tested ceramide cream"
                if long_running
                else "Big sale today",
                "body_copy": "Clinically tested with ceramides and niacinamide."
                if long_running
                else "Limited stock, 40% off, free shipping.",
                "platform": "facebook",
                "proxy_bucket": "high" if long_running else "low",
                "hook_type": "authority_expert" if long_running else "offer_led",
                "tone": "clinical" if long_running else "urgent",
            }
        )
    return rows


# --- features -------------------------------------------------------------


def test_features_include_only_the_agreed_set():
    features, names = build_features(_rows(2))
    assert set(names) == {
        "hook_type", "tone", "platform_count", "headline_length", "body_length",
        "has_offer_language", "has_ingredient_mention", "has_authority_language",
    }


def test_label_components_are_excluded_from_features():
    """days_active/variant_count ARE the label — including them leaks it."""
    _, names = build_features(_rows(2))
    assert "days_active" not in names
    assert "variant_count" not in names
    assert "proxy_bucket" not in names


def test_platform_count_replaces_the_raw_placement_list():
    """Entry #27: `platform` is a comma-separated Ad Library placement list,
    so one-hot on the raw string makes every combination its own class."""
    from creativesignal.insight.tree import platform_count

    assert platform_count("FACEBOOK,INSTAGRAM,MESSENGER") == 3
    assert platform_count("FACEBOOK,INSTAGRAM") == 2
    assert platform_count("unknown") == 0
    assert platform_count(None) == 0


def test_numeric_conditions_render_as_english_not_expressions():
    from creativesignal.insight.tree import _humanize

    assert _humanize("platform count <= 4.5") == (
        "the ad runs on 4 or fewer placement surfaces"
    )
    assert _humanize("body length > 18.5") == "the body is longer than 18 words"


@pytest.mark.parametrize(
    "bucket,phrase",
    [
        ("high", "longer"),
        ("mid", "for a moderate period"),
        ("low", "for a shorter period"),
    ],
)
def test_direction_phrase_is_correct_for_every_bucket(bucket, phrase):
    """Regression: `mid` previously rendered as "for a shorter period"."""
    assert phrase in rule_to_sentence(TreeRule(["tone_clinical"], bucket, 10, 6))


def test_advertiser_is_excluded():
    """Would memorize brands — true, useless, and reads as a brand claim."""
    _, names = build_features(_rows(2))
    assert "advertiser" not in names


def test_binary_copy_features_detect_their_vocabularies():
    [offer], _ = build_features(
        [{"headline": "", "body_copy": "40% off, free shipping", "platform": "x"}]
    )
    assert offer["has_offer_language"] == 1
    assert offer["has_ingredient_mention"] == 0

    [ingredient], _ = build_features(
        [{"headline": "", "body_copy": "with niacinamide and SPF 50", "platform": "x"}]
    )
    assert ingredient["has_ingredient_mention"] == 1


# --- refusal guards -------------------------------------------------------


def test_refuses_to_train_on_too_few_rows():
    with pytest.raises(InsufficientTreeData, match="Tier-3 curation"):
        train_tree(_rows(10))


def test_refuses_to_train_on_a_single_bucket():
    rows = _rows(60)
    for row in rows:
        row["proxy_bucket"] = "high"
    with pytest.raises(InsufficientTreeData, match="Only one proxy bucket"):
        train_tree(rows)


def test_single_bucket_error_points_at_threshold_recalibration():
    rows = _rows(60)
    for row in rows:
        row["proxy_bucket"] = "mid"
    with pytest.raises(InsufficientTreeData, match="Entry #5"):
        train_tree(rows)


# --- training -------------------------------------------------------------


def test_trains_and_respects_the_depth_cap():
    result = train_tree(_rows(60))
    assert result.model.get_depth() <= MAX_DEPTH
    assert result.n_rows == 60
    assert set(result.class_balance) == {"high", "low"}


def test_rules_are_extracted_for_every_leaf():
    result = train_tree(_rows(60))
    assert result.rules
    assert all(r.n_samples > 0 for r in result.rules)


# --- THE honesty rule (Entry #17) ----------------------------------------


def test_rule_claims_never_contain_performance_language():
    """Enforced mechanically, not by reviewer discipline.

    Checked against the generated claim only. The fixed disclaimer uses
    performance vocabulary deliberately, to negate it.
    """
    result = train_tree(_rows(60))
    for rule in result.rules:
        lowered = rule_claim(rule).lower()
        for banned in BANNED_IN_RULES:
            assert banned not in lowered, f"{banned!r} leaked into: {lowered}"


def test_every_rendered_sentence_carries_the_disclaimer():
    result = train_tree(_rows(60))
    assert all(s.endswith(DISCLAIMER) for s in rules_as_sentences(result))


def test_rule_sentence_names_the_proxy_as_a_proxy():
    rule = TreeRule(["hook_type_offer_led"], "high", 20, 15)
    sentence = rule_to_sentence(rule)
    assert "longevity-proxy bucket" in sentence
    assert "not evidence" in sentence


def test_rule_sentence_states_prevalence_with_both_numbers():
    sentence = rule_to_sentence(TreeRule(["tone_clinical"], "high", 34, 22))
    assert "34" in sentence and "22" in sentence


def test_rule_sentence_handles_the_root_only_tree():
    assert "all ads" in rule_to_sentence(TreeRule([], "mid", 10, 6))
