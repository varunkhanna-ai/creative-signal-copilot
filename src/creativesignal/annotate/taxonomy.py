"""W1.5: the frozen `hook_type` and `tone` label sets.

**Frozen.** The F2 bootstrap labels a seed set against these exact strings and
the logistic regression trains on them, so adding, renaming, or reordering a
label after the bootstrap invalidates the seed set and every annotation
already written. Changing this file means re-running W1.6 onward.

Design notes are in docs/decision-log.md Entry #8. In short: `hook_type` is
the *rhetorical device that opens the ad* and `tone` is the *register it
speaks in* — deliberately orthogonal, so a single ad gets one of each and the
pair is informative rather than redundant.
"""

from __future__ import annotations

from typing import Final

HOOK_TYPES: Final[tuple[str, ...]] = (
    "problem_solution",
    "benefit_promise",
    "social_proof",
    "authority_expert",
    "curiosity_question",
    "offer_led",
    "ingredient_led",
)

TONE_LABELS: Final[tuple[str, ...]] = (
    "clinical",
    "aspirational",
    "warm_reassuring",
    "playful",
    "urgent",
    "minimal_matter_of_fact",
)

# One-line definitions. These are the operative spec: they go verbatim into
# the bootstrap prompt (W1.6) and the human verification sheet (W1.7) so the
# LLM and the human are labeling against identical wording.
HOOK_TYPE_DEFINITIONS: Final[dict[str, str]] = {
    "problem_solution": (
        "Opens by naming a skin problem the reader has, then positions the "
        "product as the fix."
    ),
    "benefit_promise": (
        "Opens with the desirable end state the product delivers, without "
        "first naming a problem."
    ),
    "social_proof": (
        "Leads with other people — reviews, testimonials, customer counts, "
        "'#1 bestseller', before/after accounts."
    ),
    "authority_expert": (
        "Leads with expert or institutional endorsement — dermatologist "
        "recommended, clinically tested, lab results."
    ),
    "curiosity_question": (
        "Opens with a question or withheld information that the ad promises "
        "to resolve."
    ),
    "offer_led": (
        "Leads with the commercial offer — discount, bundle, free shipping, "
        "limited-time pricing."
    ),
    "ingredient_led": (
        "Leads with a named ingredient or formulation as the reason to "
        "believe — retinol, niacinamide, hyaluronic acid, SPF 50."
    ),
}

TONE_DEFINITIONS: Final[dict[str, str]] = {
    "clinical": "Precise and technical; concentrations, study language, dermatological register.",
    "aspirational": "Evokes an idealized self or life; glow, radiance, confidence, transformation.",
    "warm_reassuring": "Gentle and supportive; safe for sensitive skin, no judgment, 'we get it'.",
    "playful": "Light, humorous, or irreverent; wordplay, emoji-forward, conversational.",
    "urgent": "Pressure and immediacy; act now, selling out, last chance, countdowns.",
    "minimal_matter_of_fact": "Plain and unadorned; states what it is and what it does, no persuasion styling.",
}

# Used when the LLM cannot confidently place a row (W1.6) — an explicit
# escape hatch beats a forced wrong label, because a forced label enters the
# LR training set as noise and is invisible thereafter.
UNCLEAR_LABEL: Final[str] = "unclear"


def validate_hook_type(label: str) -> str:
    """Return `label` if it is a frozen hook type (or `unclear`); else raise."""
    if label not in HOOK_TYPES and label != UNCLEAR_LABEL:
        raise ValueError(
            f"{label!r} is not a frozen hook_type. Valid: {list(HOOK_TYPES)} "
            f"or {UNCLEAR_LABEL!r}. The taxonomy is frozen — see W1.5."
        )
    return label


def validate_tone(label: str) -> str:
    """Return `label` if it is a frozen tone (or `unclear`); else raise."""
    if label not in TONE_LABELS and label != UNCLEAR_LABEL:
        raise ValueError(
            f"{label!r} is not a frozen tone. Valid: {list(TONE_LABELS)} "
            f"or {UNCLEAR_LABEL!r}. The taxonomy is frozen — see W1.5."
        )
    return label
