"""Shared UI vocabulary. Every page uses these; no page invents its own.

Keeps the AGENTS.md component rules in one place — the honesty footer is
verbatim, creative cards render identically everywhere, and no page defines
colors (that is `.streamlit/config.toml`'s job alone).
"""

from __future__ import annotations

import html
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Literal

# Arrow's mimalloc allocator segfaults (SIGSEGV in `mi_thread_init`) when
# pyarrow submodules are first imported inside Streamlit's script-runner
# thread — it killed the server process on the first search, with no
# traceback. Switching Arrow to the system allocator fixes it. Must be set
# before pyarrow creates its default pool. See docs/decision-log.md Entry #12.
os.environ.setdefault("ARROW_DEFAULT_MEMORY_POOL", "system")

import streamlit as st

# F4 (W6.2): Streamlit Cloud's base image ships an sqlite too old for Chroma.
# Must run before chromadb is imported anywhere, so it lives at the top of
# the shared import path rather than in one page.
try:  # pragma: no cover - deploy-environment shim
    import pysqlite3  # noqa: F401

    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass  # local dev: the system sqlite is new enough

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from creativesignal.schema import HONESTY_RULE  # noqa: E402

# ---------------------------------------------------------------------------
# Shared CSS (visual polish only)
#
# What lives here vs. in .streamlit/config.toml: config.toml stays the only
# place *colors* are defined. This block covers what Streamlit theming cannot
# express at all — border radius, shadows, spacing rhythm, and the reviewer
# badge/pill shape. The only hues below are neutral rgba overlays plus the
# three reviewer-severity colors, which AGENTS.md fixes as red / amber / gray
# (the two accent colors + informational gray already used for flags).
#
# Selector note (Streamlit 1.41): st.container(border=True) renders
# div[data-testid="stVerticalBlockBorderWrapper"] with the border applied via
# a generated emotion class — there is no attribute distinguishing bordered
# wrappers from unbordered ones. creative_card() therefore emits a zero-size
# .cs-card marker, and cards are selected via :has(.cs-card).
# ---------------------------------------------------------------------------

_CSS = """<style>
:root {
  --cs-radius: 0.75rem;
  --cs-card-shadow: 0 1px 2px rgba(30, 30, 30, 0.05), 0 2px 8px rgba(30, 30, 30, 0.04);
  --cs-neutral-01: rgba(30, 30, 30, 0.035);
  --cs-neutral-02: rgba(30, 30, 30, 0.08);
  --cs-claim: #b42318;
  --cs-claim-bg: rgba(180, 35, 24, 0.08);
  --cs-claim-border: rgba(180, 35, 24, 0.30);
  --cs-similarity: #96560a;
  --cs-similarity-bg: rgba(150, 86, 10, 0.09);
  --cs-similarity-border: rgba(150, 86, 10, 0.32);
  --cs-info: #4a4a44;
  --cs-info-bg: rgba(74, 74, 68, 0.07);
  --cs-info-border: rgba(74, 74, 68, 0.25);
}

/* --- bordered containers: shared chrome -------------------------------- */
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stExpander"] details {
  border-radius: var(--cs-radius);
}

/* --- creative cards: shadow + spacing rhythm ---------------------------- */
.cs-card { display: none; }
[data-testid="stVerticalBlockBorderWrapper"]:has(.cs-card) {
  border-radius: var(--cs-radius);
  box-shadow: var(--cs-card-shadow);
  margin-bottom: 0.5rem;
}

/* --- typography hierarchy ---------------------------------------------- */
section.main h1 {
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  line-height: 1.2;
  padding-bottom: 0.25rem;
}
section.main h2 {
  font-size: 1.4rem;
  font-weight: 650;
  line-height: 1.3;
  margin-top: 0.75rem;
}
section.main h3 {
  font-size: 1.15rem;
  font-weight: 600;
  line-height: 1.35;
}
section.main [data-testid="stCaptionContainer"] {
  font-size: 0.82rem;
  line-height: 1.45;
  color: var(--cs-info);
}
section.main hr { margin: 1.75rem auto; }

/* --- buttons ------------------------------------------------------------ */
.stButton button,
[data-testid="stFormSubmitButton"] button {
  border-radius: 999px;
  font-weight: 600;
}

/* --- metrics ------------------------------------------------------------ */
[data-testid="stMetric"] {
  background: var(--cs-neutral-01);
  border-radius: var(--cs-radius);
  padding: 0.75rem 1rem;
}

/* --- reviewer badge / pill --------------------------------------------- */
.cs-badge {
  display: inline-block;
  padding: 0.12rem 0.6rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  line-height: 1.5;
  white-space: nowrap;
  border: 1px solid transparent;
}
.cs-badge--claim {
  color: var(--cs-claim);
  background: var(--cs-claim-bg);
  border-color: var(--cs-claim-border);
}
.cs-badge--similarity {
  color: var(--cs-similarity);
  background: var(--cs-similarity-bg);
  border-color: var(--cs-similarity-border);
}
.cs-badge--info {
  color: var(--cs-info);
  background: var(--cs-info-bg);
  border-color: var(--cs-info-border);
}
.cs-flag-message { font-size: 0.95rem; }

/* --- loading-state detail line ------------------------------------------ */
.cs-loading-detail {
  font-size: 0.82rem;
  color: var(--cs-info);
  margin-top: 0.25rem;
}
</style>"""


def inject_css() -> None:
    """Inject the shared CSS. Call once per page, right after set_page_config.

    Not done at import time: every page imports this module *before*
    st.set_page_config, and an st call at import time would make Streamlit
    raise "set_page_config() can only be called once" / ordering errors.
    """
    st.markdown(_CSS, unsafe_allow_html=True)


def badge(label: str, kind: Literal["claim", "similarity", "info"] = "info") -> str:
    """Pill HTML for one reviewer-style marker.

    Render with ``st.markdown(badge(...), unsafe_allow_html=True)``. Kinds map
    to the AGENTS.md flag palette: claim=red, similarity=amber, info=gray.
    The label is HTML-escaped; it is always a fixed Literal-derived string.
    """
    safe_kind = kind if kind in ("claim", "similarity", "info") else "info"
    return f'<span class="cs-badge cs-badge--{safe_kind}">{html.escape(label)}</span>'


@contextmanager
def generating(message: str = "Generating...", *, detail: str | None = None) -> Iterator[None]:
    """The app's single loading pattern for live calls (LLM / retrieval / image).

    Wraps ``st.spinner(message)`` and adds an optional styled detail line that
    is cleared when the call completes, so every live call — including the
    upcoming image-generation path — shows the same affordance.

    ``detail`` is HTML-escaped: callers pass trusted literals, never user text.
    """
    slot = st.empty()
    with st.spinner(message):
        if detail:
            slot.markdown(
                f'<p class="cs-loading-detail">{html.escape(detail)}</p>',
                unsafe_allow_html=True,
            )
        try:
            yield
        finally:
            slot.empty()


def page_header(title: str, caption: str) -> None:
    """`st.title` -> one-line caption. Identical skeleton on every page."""
    st.title(title)
    st.caption(caption)


def honesty_footer() -> None:
    """The verbatim honesty rule. Bottom of every page, no exceptions."""
    st.divider()
    st.caption(HONESTY_RULE)


def creative_card(result, show_scores: bool = False) -> None:
    """Render one retrieved creative: bordered container, provenance footer.

    `result` is a RetrievedCreative or anything with `.creative`.
    """
    creative = getattr(result, "creative", result)
    with st.container(border=True):
        # Zero-size marker lets the shared CSS target bordered *cards* via
        # :has(.cs-card) — 1.41 gives bordered containers no usable attribute.
        st.markdown('<span class="cs-card"></span>', unsafe_allow_html=True)
        st.markdown(f"**{creative.headline or '(no headline)'}**")
        if creative.body_copy:
            st.write(creative.body_copy)

        provenance = " · ".join(
            [
                creative.advertiser,
                creative.platform,
                creative.date_observed.isoformat(),
            ]
        )
        if creative.source_url:
            provenance += f" · [source]({creative.source_url})"
        else:
            provenance += " · no source link (synthetic corpus)"
        st.caption(f"`{creative.creative_id}` · {provenance}")

        if show_scores and hasattr(result, "score"):
            with st.expander("Why this was retrieved"):
                st.write(
                    f"Fused score **{result.score:.3f}** "
                    f"(semantic {result.semantic_score:.3f}, "
                    f"keyword {result.keyword_score:.3f})"
                )
                st.caption(
                    "Matched via: "
                    + ", ".join(result.matched_representations or ["unknown"])
                )
                st.caption(
                    "Score is retrieval similarity — a match on wording, not "
                    "evidence that this ad performed."
                )


def empty_state(message: str) -> None:
    """One helpful sentence, never a blank pane or a stack trace."""
    st.info(message)


def corpus_warning() -> None:
    """Surface the corpus gap in the product itself, not only in the docs."""
    from creativesignal.sources.curated import CuratedCorpusConnector

    try:
        creatives = CuratedCorpusConnector().all_creatives()
    except FileNotFoundError:
        st.error("No corpus found. Run `make download && make ingest` first.")
        return

    tier3 = sum(1 for c in creatives if c.source_type == "tier3")
    if tier3 == 0:
        st.warning(
            f"Corpus is {len(creatives)} synthetic Tier-2 ads with no provenance. "
            "Tier-3 curation (the real, source-linked Meta Ad Library sample) "
            "is outstanding, so retrieval quality here is not representative "
            "and no eval numbers are published. See docs/decision-log.md."
        )


def render_trace(trace) -> None:
    """W3.3: the agent's plan->tools->evidence path, collapsed by default."""
    with st.expander("How this was produced"):
        for i, step in enumerate(trace.steps, start=1):
            st.markdown(f"{i}. **{step.name}** — {step.duration_s:.2f}s")
            if step.inputs:
                st.code(
                    "\n".join(f"{k}={v!r}" for k, v in step.inputs.items()),
                    language="python",
                )
            if step.error:
                st.error(step.error)
            elif step.output_summary:
                st.caption(step.output_summary)
        for note in trace.notes:
            st.caption(f"Note: {note}")


# Reviewer severities -> badge kinds. The red/amber/gray palette itself lives
# in the CSS block above (the only flags palette the UI direction allows).
_FLAG_KIND = {"claim": "claim", "similarity": "similarity", "info": "info"}


def reviewer_flags(review) -> None:
    """Render reviewer flags inline on a concept, evidence on expand.

    Flags are CSS pills via badge(); the flag-line → evidence-expander
    structure is unchanged so the concept-display layout stays stable for
    parallel work on this section.
    """
    if review is None:
        return
    if not review.flags:
        st.markdown(badge("No flags raised", "info"), unsafe_allow_html=True)
        return

    for flag in review.flags:
        kind = _FLAG_KIND.get(flag.severity, "info")
        st.markdown(
            f'{badge(flag.severity.upper(), kind)} '
            f'<span class="cs-flag-message">{html.escape(flag.message)}</span>',
            unsafe_allow_html=True,
        )
        with st.expander("Evidence for this flag"):
            st.write(flag.evidence)
            if flag.span:
                st.caption(f"Matched text: {flag.span!r}")
            if flag.related_creative_ids:
                st.caption(f"Related: {', '.join(flag.related_creative_ids)}")


def live_mode_allowed() -> bool:
    """W6.1b: live generation is gated behind a password when deployed.

    Locally (no deploy secrets configured) live mode is simply on. On the
    deployed app it requires `st.secrets["demo_password"]`, so no
    unauthenticated visitor can spend API credits.
    """
    try:
        expected = st.secrets["demo_password"]
    except Exception:
        return True  # no deploy secrets present -> local dev

    if st.session_state.get("live_unlocked"):
        return True
    supplied = st.sidebar.text_input("Demo password", type="password")
    if supplied and supplied == expected:
        st.session_state["live_unlocked"] = True
        return True
    return False
