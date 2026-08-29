"""W1.5: the taxonomy is frozen — these tests are the freeze.

If a label is added, renamed, or removed, these fail loudly. That is the
point: the F2 seed set and every annotation already written are keyed to
these exact strings.
"""

from __future__ import annotations

import pytest

from creativesignal.annotate.taxonomy import (
    HOOK_TYPE_DEFINITIONS,
    HOOK_TYPES,
    TONE_DEFINITIONS,
    TONE_LABELS,
    UNCLEAR_LABEL,
    validate_hook_type,
    validate_tone,
)


def test_label_counts_are_in_the_specified_range():
    """W1.5 specifies 6-8 labels each."""
    assert 6 <= len(HOOK_TYPES) <= 8
    assert 6 <= len(TONE_LABELS) <= 8


def test_labels_are_unique():
    assert len(set(HOOK_TYPES)) == len(HOOK_TYPES)
    assert len(set(TONE_LABELS)) == len(TONE_LABELS)


def test_hook_and_tone_label_sets_do_not_overlap():
    """The two axes must stay orthogonal — a shared label means they aren't."""
    assert not set(HOOK_TYPES) & set(TONE_LABELS)


def test_every_label_has_a_definition():
    """Definitions are the operative spec — they go into the prompt verbatim."""
    assert set(HOOK_TYPE_DEFINITIONS) == set(HOOK_TYPES)
    assert set(TONE_DEFINITIONS) == set(TONE_LABELS)
    assert all(d.strip() for d in HOOK_TYPE_DEFINITIONS.values())
    assert all(d.strip() for d in TONE_DEFINITIONS.values())


def test_frozen_label_sets_exactly():
    """Change detector by design — see the module docstring."""
    assert HOOK_TYPES == (
        "problem_solution",
        "benefit_promise",
        "social_proof",
        "authority_expert",
        "curiosity_question",
        "offer_led",
        "ingredient_led",
    )
    assert TONE_LABELS == (
        "clinical",
        "aspirational",
        "warm_reassuring",
        "playful",
        "urgent",
        "minimal_matter_of_fact",
    )


@pytest.mark.parametrize("label", HOOK_TYPES)
def test_validate_accepts_every_hook_type(label):
    assert validate_hook_type(label) == label


@pytest.mark.parametrize("label", TONE_LABELS)
def test_validate_accepts_every_tone(label):
    assert validate_tone(label) == label


def test_validate_accepts_unclear():
    """An explicit escape hatch beats a forced wrong label entering training."""
    assert validate_hook_type(UNCLEAR_LABEL) == UNCLEAR_LABEL
    assert validate_tone(UNCLEAR_LABEL) == UNCLEAR_LABEL


def test_validate_rejects_unknown_label():
    with pytest.raises(ValueError, match="not a frozen hook_type"):
        validate_hook_type("storytelling")
    with pytest.raises(ValueError, match="not a frozen tone"):
        validate_tone("sassy")


def test_validate_rejects_cross_axis_label():
    """A tone is not a hook type, even though both are valid strings."""
    with pytest.raises(ValueError):
        validate_hook_type("clinical")
    with pytest.raises(ValueError):
        validate_tone("offer_led")
