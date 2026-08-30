"""W4.1/W4.6/W6.1b: brief -> trace -> evidence -> concepts -> reviewer flags -> export.

The money path. Two modes (W6.1b):
  - **Demo** (default when deployed): replays a stored run from the `runs`
    table. No API call, instant, costs nothing.
  - **Live**: runs the agent. Requires the demo password when deployed;
    locally, with no deploy secrets present, live is simply available.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from shared import (
    creative_card,
    empty_state,
    generating,
    honesty_footer,
    inject_css,
    live_mode_allowed,
    page_header,
    render_trace,
    reviewer_flags,
)

from creativesignal.agents.analyst import Brief, run_analyst
from creativesignal.agents.reviewer import evidence_map, review_all
from creativesignal.export import export_filename, run_to_markdown
from creativesignal.llm import has_api_key
from creativesignal.runs import build_run, list_runs, load_run, save_run
from creativesignal.sources.curated import CuratedCorpusConnector

st.set_page_config(page_title="Brief to concepts — CreativeSignal", layout="wide")
inject_css()

page_header(
    "Brief to concepts",
    "Submit a brief; get evidence-backed concepts with an independent policy review.",
)

past_runs = list_runs(limit=25)
live_allowed = live_mode_allowed()

with st.sidebar:
    st.subheader("Mode")
    mode = st.radio(
        "Generation mode",
        ["Demo (replay a saved run)", "Live (call the model)"],
        index=0 if past_runs else 1,
        label_visibility="collapsed",
    )
    demo_mode = mode.startswith("Demo")
    if not demo_mode and not live_allowed:
        st.error(
            "Live mode is password-protected on the deployed app. Enter the "
            "demo password in the sidebar to enable it."
        )
    st.caption(
        "Demo mode replays stored runs with zero API calls. Live mode runs "
        "the agent and costs tokens."
    )

# --- demo mode: replay ----------------------------------------------------

if demo_mode:
    if not past_runs:
        empty_state(
            "No saved runs to replay yet. Switch to Live mode and generate one — "
            "it will be persisted and become replayable here."
        )
        honesty_footer()
        st.stop()

    labels = {
        f"{r.created_at:%Y-%m-%d %H:%M} — {r.brief.get('text', '')[:50]}": r.run_id
        for r in past_runs
    }
    chosen = st.selectbox("Saved run", list(labels))
    run = load_run(labels[chosen])
    st.caption(f"Replaying `{run.run_id}` — no API call was made.")

# --- live mode: generate --------------------------------------------------

else:
    with st.form("brief"):
        text = st.text_area(
            "Campaign brief",
            placeholder="e.g. a hydrating serum for sensitive skin, "
            "dermatologist-backed tone",
            height=90,
        )
        columns = st.columns(2)
        audience = columns[0].text_input("Audience", placeholder="women 25-40")
        objective = columns[1].text_input("Objective", placeholder="awareness")
        tone = columns[0].text_input("Tone", placeholder="clinical, reassuring")
        prohibited = columns[1].text_input(
            "Prohibited claims", placeholder="no medical claims"
        )
        generate = st.form_submit_button("Generate concepts")

    if not generate:
        empty_state("Fill in the brief and press Generate.")
        honesty_footer()
        st.stop()

    if not live_allowed:
        st.error("Live mode is not unlocked. Enter the demo password in the sidebar.")
        honesty_footer()
        st.stop()

    if not has_api_key():
        st.error(
            "No ANTHROPIC_API_KEY configured. Retrieval works without one, but "
            "concept generation needs it — add it to .env locally or to "
            "Streamlit secrets when deployed."
        )
        honesty_footer()
        st.stop()

    brief = Brief(
        text=text,
        audience=audience,
        objective=objective,
        tone=tone,
        prohibited_claims=prohibited,
    )
    with generating(
        "Retrieving evidence and generating concepts...",
        detail="A live run typically takes 15–30 seconds.",
    ):
        result = run_analyst(brief)

        if result.clarifying_question:
            st.warning(result.clarifying_question)
            render_trace(result.trace)
            honesty_footer()
            st.stop()

        source = CuratedCorpusConnector()
        creatives = [c for c in (source.get(i) for i in result.retrieved_ids) if c]
        reviews = review_all(
            result.concepts,
            evidence_map(creatives),
            has_promotion=bool(prohibited and "promo" in prohibited.lower()),
        )
        run = build_run(
            brief=brief.as_dict(),
            retrieved_creative_ids=result.retrieved_ids,
            trend_report=result.trend_report,
            concepts=result.concepts,
            review_results=reviews,
        )
        save_run(run)

    st.success(f"Saved as `{run.run_id}` — replayable in demo mode.")
    render_trace(result.trace)

# --- render (identical for both modes) ------------------------------------

report = run.trend_report
if report:
    st.subheader("Trend report")
    if report.patterns:
        for pattern in report.patterns:
            st.markdown(
                f"- **{pattern.description}** — {pattern.prevalence_statement}."
            )
    else:
        st.info(
            "No prevalence patterns reported for this run. "
            + (report.confidence_note or "")
        )
    for counter in report.counter_examples:
        st.caption(f"Counter-example: {counter}")
    if report.confidence_note and report.patterns:
        st.caption(report.confidence_note)
    st.caption(report.coverage_statement)

st.subheader("Evidence")
source = CuratedCorpusConnector()
retrieved = [c for c in (source.get(i) for i in run.retrieved_creative_ids) if c]
if retrieved:
    for creative in retrieved:
        creative_card(creative)
else:
    empty_state("No evidence was retrieved for this run.")

st.subheader("Concepts")
reviews_by_title = {r.concept_title: r for r in run.review_results}
if not run.concepts:
    empty_state(
        "No concepts passed the citation self-check. A concept that cites "
        "evidence it was not given does not ship."
    )
for i, concept in enumerate(run.concepts, start=1):
    with st.container(border=True):
        st.markdown(f"**{i}. {concept.title}**")
        if concept.hook_type:
            st.caption(f"Hook: {concept.hook_type}")
        st.markdown(f"**{concept.headline}**")
        st.write(concept.body_copy)
        if concept.rationale:
            st.caption(f"Why this concept: {concept.rationale}")
        st.caption(
            "Cites: " + (", ".join(f"`{c}`" for c in concept.cited_creative_ids) or "none")
        )
        reviewer_flags(reviews_by_title.get(concept.title))

st.subheader("Export")
source_urls = {c.creative_id: c.source_url for c in retrieved if c.source_url}
markdown = run_to_markdown(run, source_urls)
st.download_button(
    "Download Markdown",
    data=markdown,
    file_name=export_filename(run),
    mime="text/markdown",
)
with st.expander("Preview export"):
    st.code(markdown, language="markdown")

honesty_footer()
