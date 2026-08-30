"""W2.9: search the corpus, view cited cards with provenance.

Also carries the W5.10b corpus-health panel (stretch): record counts by
tier, label distributions, escalation rate, rights-note coverage — the
data-governance story made visible in the demo rather than only in a doc.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from shared import (
    corpus_warning,
    creative_card,
    empty_state,
    honesty_footer,
    inject_css,
    page_header,
)

from creativesignal.retrieval.hybrid import hybrid_search
from creativesignal.sources.base import SearchFilters

st.set_page_config(page_title="Explore — CreativeSignal", layout="wide")
inject_css()

page_header(
    "Explore the corpus",
    "Search curated skincare ads and inspect the provenance behind every record.",
)
corpus_warning()


@st.cache_data(show_spinner=False)
def corpus_stats() -> dict:
    """Counts for the health panel. Cached — it's a full table scan."""
    import sqlite3

    from creativesignal.sources.curated import DB_PATH

    with sqlite3.connect(DB_PATH) as conn:
        by_tier = dict(
            conn.execute("SELECT source_type, COUNT(*) FROM creatives GROUP BY source_type")
        )
        total = conn.execute("SELECT COUNT(*) FROM creatives").fetchone()[0]
        with_rights = conn.execute(
            "SELECT COUNT(*) FROM creatives WHERE rights_note IS NOT NULL "
            "AND rights_note != '' AND rights_note NOT LIKE '%MISSING%'"
        ).fetchone()[0]
        with_source = conn.execute(
            "SELECT COUNT(*) FROM creatives WHERE source_url IS NOT NULL"
        ).fetchone()[0]
        hooks = dict(
            conn.execute(
                "SELECT hook_type, COUNT(*) FROM annotations WHERE hook_type IS NOT NULL "
                "GROUP BY hook_type ORDER BY COUNT(*) DESC"
            )
        )
        annotators = dict(
            conn.execute("SELECT annotator, COUNT(*) FROM annotations GROUP BY annotator")
        )
    return {
        "by_tier": by_tier,
        "total": total,
        "with_rights": with_rights,
        "with_source": with_source,
        "hooks": hooks,
        "annotators": annotators,
    }


with st.sidebar:
    st.subheader("Filters")
    tier = st.selectbox("Tier", ["any", "tier1", "tier2", "tier3"])
    platform = st.text_input("Platform", placeholder="facebook, instagram, tiktok")
    bucket = st.selectbox("Longevity proxy", ["any", "high", "mid", "low"])
    st.caption("Longevity proxy is a spend-persistence signal, not performance.")
    limit = st.slider("Results", min_value=3, max_value=20, value=5)

# A form, not a bare text_input: the search triggers an embedding pass, so
# re-running on every keystroke would be wasteful and visibly laggy.
with st.form("search"):
    query = st.text_input(
        "Search", placeholder="e.g. gentle cleanser for sensitive skin"
    )
    submitted = st.form_submit_button("Search")

if query:
    filters = SearchFilters(
        source_type=None if tier == "any" else tier,
        platform=platform.strip() or None,
        proxy_bucket=None if bucket == "any" else bucket,
    )
    response = hybrid_search(query, limit=limit, filters=filters)

    if not response.results:
        empty_state(
            "Nothing matched. Try broader wording, or clear the sidebar filters — "
            "the corpus is small, so narrow filters often exclude everything."
        )
    else:
        st.caption(
            f"{len(response.results)} results"
            + (f" · filters: {response.filters_applied}" if response.filters_applied else "")
        )
        for result in response.results:
            creative_card(result, show_scores=True)
        st.caption(response.coverage_statement)
else:
    empty_state("Enter a search above to retrieve cited creative cards.")

with st.expander("Corpus health"):
    stats = corpus_stats()
    columns = st.columns(4)
    columns[0].metric("Creatives", stats["total"])
    columns[1].metric("Tier-3 (provenance-rich)", stats["by_tier"].get("tier3", 0))
    columns[2].metric(
        "Rights note recorded",
        f"{stats['with_rights'] / stats['total']:.0%}" if stats["total"] else "—",
    )
    columns[3].metric(
        "Has source link",
        f"{stats['with_source'] / stats['total']:.0%}" if stats["total"] else "—",
    )

    st.caption("Records by tier")
    st.dataframe(
        [{"tier": k, "records": v} for k, v in sorted(stats["by_tier"].items())],
        column_config={"tier": "Tier", "records": "Records"},
        hide_index=True,
        use_container_width=True,
    )

    if stats["hooks"]:
        st.caption("hook_type distribution")
        st.dataframe(
            [{"hook_type": k, "count": v} for k, v in stats["hooks"].items()],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.caption("No annotations yet — run `make annotate` (needs an API key).")

    if stats["annotators"]:
        escalated = sum(v for k, v in stats["annotators"].items() if k != "logreg")
        total_annotations = sum(stats["annotators"].values())
        st.metric(
            "LLM escalation rate",
            f"{escalated / total_annotations:.0%}" if total_annotations else "—",
        )

honesty_footer()
