"""W3.9: tree viz, feature importance, and a trend report with a visible trace."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from shared import empty_state, honesty_footer, page_header, render_trace

from creativesignal.agents.analyst import Brief, run_analyst
from creativesignal.insight.tree import (
    InsufficientTreeData,
    load_training_rows,
    rules_as_sentences,
    save_importance_plot,
    save_tree_plot,
    train_tree,
)

st.set_page_config(page_title="Insights — CreativeSignal", layout="wide")

page_header(
    "Insights",
    "Interpretable patterns over the corpus, and a cited trend report on demand.",
)

# --- longevity-proxy tree -------------------------------------------------

st.subheader("Longevity-proxy patterns")
st.caption(
    "A depth-3 decision tree over an ad-longevity proxy. The proxy records how "
    "long an advertiser kept running an ad — a spend-persistence signal, not a "
    "performance measurement."
)

rows = load_training_rows()
try:
    result = train_tree(rows)
except InsufficientTreeData as exc:
    empty_state(
        f"The tree cannot be trained yet: {exc} "
        "The model, its rules, and this page are built and tested; they need "
        "Tier-3 curation to produce real output."
    )
    result = None

if result is not None:
    columns = st.columns(3)
    columns[0].metric("Training rows", result.n_rows)
    columns[1].metric("Tree depth", result.model.get_depth(), delta="cap 3", delta_color="off")
    columns[2].metric("In-sample accuracy", f"{result.accuracy:.0%}")
    st.caption(
        "In-sample accuracy on a small corpus is directional only — it "
        "describes fit to this data, not generalization."
    )

    st.markdown("**Rules**")
    for sentence in rules_as_sentences(result):
        st.markdown(f"- {sentence}")

    columns = st.columns(2)
    with columns[0]:
        st.image(str(save_tree_plot(result)), caption="Decision tree")
    with columns[1]:
        st.image(str(save_importance_plot(result)), caption="Split importance")

st.divider()

# --- trend report on demand ----------------------------------------------

st.subheader("Generate a trend report")
with st.form("trend"):
    question = st.text_input(
        "Question", placeholder="e.g. how do skincare ads open in this corpus?"
    )
    submitted = st.form_submit_button("Generate report")

if submitted and question:
    with st.spinner("Retrieving evidence..."):
        # Concepts are the other page's job; this is the report path only.
        analysis = run_analyst(
            Brief(text=question, audience="general"), with_concepts=False
        )
    render_trace(analysis.trace)

    report = analysis.trend_report
    if report.patterns:
        for pattern in report.patterns:
            st.markdown(f"- **{pattern.description}** — {pattern.prevalence_statement}.")
    else:
        st.info(report.confidence_note)

    for counter in report.counter_examples:
        st.caption(f"Counter-example: {counter}")

    st.markdown("**Evidence**")
    st.caption(", ".join(f"`{c}`" for c in report.retrieved_creative_ids) or "none")
    st.caption(report.coverage_statement)
elif submitted:
    empty_state("Enter a question first.")

honesty_footer()
