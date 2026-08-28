"""CreativeSignal app entrypoint.

Page skeleton only — real content lands in later tasks per implementation.md.
The honesty footer below is verbatim from AGENTS.md and appears on every page.
"""

import streamlit as st

HONESTY_FOOTER = (
    "Every insight is traceable to examples; every recommendation is a "
    "hypothesis, not a performance claim."
)

st.set_page_config(page_title="CreativeSignal", layout="wide")

st.title("CreativeSignal")
st.caption("Evidence-backed creative-intelligence copilot for skincare ads.")

st.sidebar.title("Navigation")
st.sidebar.caption("Use the pages above to move through the app.")

st.info("Content built in later tasks.")

st.caption(HONESTY_FOOTER)
