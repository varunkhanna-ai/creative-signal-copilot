"""W4.5: the independent reviewer agent. Rules from decision-log Entry #15.

Four checks: unsupported efficacy claim, false scarcity, prohibited
targeting, and similarity-vs-retrieved. All four are **deterministic** — no
LLM call, so the reviewer runs with no API key and returns the same verdict
every time. That matters twice over: the planted-violation test (W4.9) must
be reproducible, and a reviewer whose verdict drifts run-to-run is not a
control.

The reviewer is independent of the generator on purpose: it re-reads the
concept against the retrieved evidence rather than trusting the generator's
own account of what it did.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from creativesignal.schema import Concept, ReviewFlag, ReviewResult

# --- rule vocabularies (Entry #15) ---------------------------------------

EFFICACY_PATTERNS: tuple[str, ...] = (
    r"clinically proven", r"clinically tested", r"dermatologist (?:tested|recommended|approved)",
    r"fda[- ]approved", r"medical[- ]grade", r"cures?\b", r"heals?\b",
    r"eliminates?\b", r"permanent(?:ly)?\b", r"reverses?\b", r"repairs? damage",
    r"scientifically proven", r"guaranteed results",
)
# Quantified outcome claims: "reduces wrinkles by 47%", "results in 7 days".
QUANTIFIED_CLAIM = re.compile(
    r"\b(?:\d{1,3}\s?%|\d+\s?(?:days?|weeks?))\b.{0,40}"
    r"(?:reduc|improv|clear|fade|brighten|result|visible)"
    r"|(?:reduc|improv|clear|fade|brighten|result|visible)\w*.{0,40}"
    r"\b(?:\d{1,3}\s?%|\d+\s?(?:days?|weeks?))\b",
    re.IGNORECASE,
)

SCARCITY_PATTERNS: tuple[str, ...] = (
    r"limited stock", r"only \d+ left", r"today only", r"last chance",
    r"ends tonight", r"while supplies last", r"selling out", r"act now",
    r"hurry\b", r"don'?t miss out",
)

TARGETING_PATTERNS: tuple[str, ...] = (
    r"problem skin", r"fix your face", r"nobody wants", r"look old(?:er)?",
    r"embarrassing\b", r"ashamed\b", r"too dark", r"too pale",
    r"stop looking\b", r"before it'?s too late",
)

SIMILARITY_THRESHOLD = 0.6  # W4.4


def _find(patterns: tuple[str, ...], text: str) -> list[str]:
    """Return the literal matched spans for `patterns` in `text`."""
    found = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            found.append(match.group(0))
    return found


def _concept_text(concept: Concept) -> str:
    return f"{concept.headline} {concept.body_copy}".strip()


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def jaccard(a: str, b: str) -> float:
    """Token overlap / union. Explainable in one sentence, and showable."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# --- the four checks ------------------------------------------------------


def check_unsupported_claims(
    concept: Concept, evidence: dict[str, str]
) -> list[ReviewFlag]:
    """Flag efficacy claims not present in any cited retrieved creative.

    The reviewer cannot judge whether a claim is *true*. It judges whether
    the evidence the concept cites actually contains it — an unsupported
    claim is one the generator invented.
    """
    text = _concept_text(concept)
    spans = _find(EFFICACY_PATTERNS, text)
    spans += [m.group(0) for m in QUANTIFIED_CLAIM.finditer(text)]

    cited_text = " ".join(
        evidence.get(cid, "") for cid in concept.cited_creative_ids
    ).lower()

    flags = []
    for span in dict.fromkeys(spans):  # dedupe, keep order
        supported = span.lower() in cited_text
        if supported:
            continue
        flags.append(
            ReviewFlag(
                check="unsupported_claim",
                severity="claim",
                message=f"Efficacy claim {span!r} is not supported by the cited evidence.",
                evidence=(
                    f"The concept states {span!r}. None of the cited creatives "
                    f"({', '.join(concept.cited_creative_ids) or 'none cited'}) "
                    "contain this claim, so it was introduced by the generator "
                    "rather than drawn from a retrieved example."
                ),
                span=span,
                related_creative_ids=list(concept.cited_creative_ids),
            )
        )
    return flags


def check_false_scarcity(concept: Concept, has_promotion: bool = False) -> list[ReviewFlag]:
    """Flag urgency language when the brief supplies no real promotion window."""
    if has_promotion:
        return []
    spans = _find(SCARCITY_PATTERNS, _concept_text(concept))
    return [
        ReviewFlag(
            check="false_scarcity",
            severity="claim",
            message=f"Scarcity language {span!r} with no stated promotion window.",
            evidence=(
                f"The concept uses {span!r}, which asserts limited availability. "
                "The brief specifies no promotion or inventory window, so this "
                "urgency is unsubstantiated. Note: every ad in the current "
                "corpus contains scarcity language, so this pattern is inherited "
                "from thin source data (docs/decision-log.md B2)."
            ),
            span=span,
        )
        for span in dict.fromkeys(spans)
    ]


def check_prohibited_targeting(concept: Concept) -> list[ReviewFlag]:
    """Flag appearance-shaming or protected-attribute targeting language."""
    spans = _find(TARGETING_PATTERNS, _concept_text(concept))
    return [
        ReviewFlag(
            check="prohibited_targeting",
            severity="claim",
            message=f"Potentially prohibited targeting language: {span!r}.",
            evidence=(
                f"The phrase {span!r} frames the audience in terms of a personal "
                "inadequacy or a protected attribute. Ad platforms restrict "
                "copy that implies a personal characteristic."
            ),
            span=span,
        )
        for span in dict.fromkeys(spans)
    ]


def check_similarity(
    concept: Concept, evidence: dict[str, str], threshold: float = SIMILARITY_THRESHOLD
) -> list[ReviewFlag]:
    """Flag concepts too close to a specific retrieved ad. Advisory, not blocking."""
    text = _concept_text(concept)
    flags = []
    for creative_id, creative_text in evidence.items():
        score = jaccard(text, creative_text)
        if score < threshold:
            continue
        shared = sorted(_tokens(text) & _tokens(creative_text))
        flags.append(
            ReviewFlag(
                check="similarity",
                severity="similarity",
                message=(
                    f"Concept is {score:.0%} token-similar to retrieved ad {creative_id}."
                ),
                evidence=(
                    f"Jaccard token overlap {score:.2f} (threshold {threshold}). "
                    f"Shared terms: {', '.join(shared[:15])}"
                    + ("..." if len(shared) > 15 else "")
                    + ". Close paraphrase of an existing advertiser's ad is a "
                    "derivative-work risk worth a human's judgment."
                ),
                related_creative_ids=[creative_id],
            )
        )
    return flags


def review_concept(
    concept: Concept,
    evidence: dict[str, str],
    has_promotion: bool = False,
    similarity_threshold: float = SIMILARITY_THRESHOLD,
) -> ReviewResult:
    """Run all four checks over one concept.

    `evidence` maps creative_id -> that creative's copy, for every creative
    retrieved for this run (not only the ones the concept cites — similarity
    must be checked against everything the generator could have seen).
    """
    flags: list[ReviewFlag] = []
    flags += check_unsupported_claims(concept, evidence)
    flags += check_false_scarcity(concept, has_promotion)
    flags += check_prohibited_targeting(concept)
    flags += check_similarity(concept, evidence, similarity_threshold)

    if not concept.is_cited:
        flags.append(
            ReviewFlag(
                check="unsupported_claim",
                severity="claim",
                message="Concept cites no evidence.",
                evidence=(
                    "Every recommendation must be traceable to retrieved "
                    "examples. This concept cites none, so nothing in it can "
                    "be checked against the corpus."
                ),
            )
        )

    return ReviewResult(
        concept_title=concept.title,
        flags=flags,
        checks_run=[
            "unsupported_claim", "false_scarcity", "prohibited_targeting", "similarity"
        ],
        reviewed_at=datetime.now(timezone.utc),
    )


def review_all(
    concepts: list[Concept], evidence: dict[str, str], has_promotion: bool = False
) -> list[ReviewResult]:
    return [review_concept(c, evidence, has_promotion) for c in concepts]


def evidence_map(creatives) -> dict[str, str]:
    """Build the {creative_id: copy} map the checks expect."""
    return {
        c.creative_id: f"{c.headline or ''} {c.body_copy or ''}".strip()
        for c in creatives
    }
