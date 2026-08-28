"""Insights page: decision-tree viz, feature importance, trend report.

Skeleton only — the intelligence layer lands in W3.6–W3.9.
"""

import streamlit as st

HONESTY_FOOTER = (
    "Every insight is traceable to examples; every recommendation is a "
    "hypothesis, not a performance claim."
)

st.title("Insights")
st.caption("Interpretable patterns from the corpus — descriptive, not causal.")

st.info("Content built in later tasks.")

st.caption(HONESTY_FOOTER)
