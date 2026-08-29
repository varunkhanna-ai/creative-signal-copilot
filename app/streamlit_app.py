"""CreativeSignal — app entrypoint.

The F4 sqlite shim lives at the very top of `shared.py`, which every page
imports before touching Chroma.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from shared import corpus_warning, honesty_footer, page_header

st.set_page_config(page_title="CreativeSignal", layout="wide")

page_header(
    "CreativeSignal",
    "Evidence-backed creative intelligence for skincare advertising.",
)

corpus_warning()

st.markdown(
    """
**What this does.** Submit a campaign brief; CreativeSignal retrieves cited
examples from a curated public corpus, produces a trend report and three
reviewable ad concepts, and runs an independent reviewer over them to flag
policy issues.

**What it does not do.** It has no performance data — no clicks, no spend, no
conversions. Nothing here tells you what works. It tells you what is *present*
in a corpus of real ads, with a link to every example.
"""
)

st.subheader("Pages")
for name, description in [
    ("Explore", "Search the corpus; inspect provenance behind every record."),
    ("Brief to concepts", "Brief in, evidence and three reviewed concepts out."),
    ("Insights", "Interpretable patterns and the longevity-proxy tree."),
    ("Eval dashboard", "Retrieval and generation metrics against targets."),
]:
    with st.container(border=True):
        st.markdown(f"**{name}**")
        st.caption(description)

honesty_footer()
