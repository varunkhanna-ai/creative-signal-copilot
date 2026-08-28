"""Brief-to-concepts page: brief form → trace → evidence → 3 concepts →
reviewer flags → export.

Skeleton only — the pipeline lands across W4.1–W4.7.
"""

import streamlit as st

HONESTY_FOOTER = (
    "Every insight is traceable to examples; every recommendation is a "
    "hypothesis, not a performance claim."
)

st.title("Brief to Concepts")
st.caption("Turn a campaign brief into three evidence-backed, reviewable ad concepts.")

st.info("Content built in later tasks.")

st.caption(HONESTY_FOOTER)
