"""Shared UI vocabulary. Every page uses these; no page invents its own.

Keeps the AGENTS.md component rules in one place — the honesty footer is
verbatim, creative cards render identically everywhere, and no page defines
colors (that is `.streamlit/config.toml`'s job alone).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

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
