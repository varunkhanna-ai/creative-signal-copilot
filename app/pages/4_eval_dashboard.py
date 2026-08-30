"""W5.10: results vs. §11 targets, with sample sizes and honest gaps.

The dashboard's job is to be *credible*, which means it must show what has
not been measured as clearly as what has. Where a metric has no data, it says
so and names the task that would produce it — it never renders a zero as
though it were a result.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from shared import empty_state, honesty_footer, inject_css, page_header

from creativesignal.annotate.escalate import CONFIDENCE_THRESHOLD, escalation_stats_from_db
from creativesignal.eval.metrics import load_golden_set
from creativesignal.llm import COST_LOG, total_spend

st.set_page_config(page_title="Eval — CreativeSignal", layout="wide")
inject_css()

RESULTS_DIR = Path("eval/results")

# §11 targets. Shown as the delta reference on every metric.
TARGETS = {
    "recall@5": 0.70,
    "precision@5": 0.60,
    "citation_correctness": 0.95,
    "groundedness": 0.80,
}

page_header(
    "Evaluation",
    "Retrieval and generation metrics against targets, with sample sizes.",
)


def latest_results() -> dict | None:
    files = sorted(RESULTS_DIR.glob("retrieval_eval_*.json"))
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding="utf-8"))


# --- retrieval ------------------------------------------------------------

st.subheader("Retrieval")

golden = []
try:
    golden = load_golden_set()
except FileNotFoundError:
    pass

results = latest_results()
if not results or not golden:
    empty_state(
        "No retrieval eval has been run. The golden set (W2.6) is not built "
        "yet, and the corpus is 9 synthetic ads — metrics over a corpus that "
        "small would be noise, not measurement. This panel deliberately shows "
        "nothing rather than a misleading zero. See docs/decision-log.md B1/B2."
    )
    st.markdown("**Targets this panel will report against**")
    st.dataframe(
        [
            {"metric": name, "target": target, "measured": "not yet measured"}
            for name, target in TARGETS.items()
        ],
        column_config={
            "metric": "Metric", "target": "§11 target", "measured": "Measured"
        },
        hide_index=True,
        use_container_width=True,
    )
else:
    st.caption(f"Golden set: {len(golden)} queries · k={results['k']}")
    st.dataframe(
        [
            {
                "condition": s["condition"],
                "n": s["n_queries"],
                "recall@5": s["recall@k"],
                "precision@5": s["precision@k"],
            }
            for s in results["summaries"]
        ],
        hide_index=True,
        use_container_width=True,
    )
    hybrid = next(
        (s for s in results["summaries"] if s["condition"] == "hybrid"), None
    )
    if hybrid:
        columns = st.columns(2)
        columns[0].metric(
            "Recall@5",
            f"{hybrid['recall@k']:.2f}",
            delta=f"{hybrid['recall@k'] - TARGETS['recall@5']:+.2f} vs target",
        )
        columns[1].metric(
            "Precision@5",
            f"{hybrid['precision@k']:.2f}",
            delta=f"{hybrid['precision@k'] - TARGETS['precision@5']:+.2f} vs target",
        )
    if len(golden) < 10:
        st.warning(
            f"{len(golden)} golden queries is below the 10-query floor — these "
            "numbers are directional at best."
        )

st.divider()

# --- annotator ------------------------------------------------------------

st.subheader("Annotator (Job A)")
try:
    stats = escalation_stats_from_db()
except Exception:
    stats = None

if not stats or stats.total == 0:
    empty_state(
        "No annotations written yet. Run `make annotate` — it needs an API key "
        "for the bootstrap pass (docs/decision-log.md B3), and the classifier "
        "needs more than 9 rows to train honestly (B2)."
    )
else:
    columns = st.columns(3)
    columns[0].metric("Annotations", stats.total)
    columns[1].metric("Kept by logistic regression", stats.kept)
    columns[2].metric(
        "Escalated to LLM",
        f"{stats.escalation_rate:.0%}",
        help=f"Confidence threshold {CONFIDENCE_THRESHOLD}",
    )
    st.caption(
        "Escalation rate is the cost lever: every escalated row is an LLM "
        "call, every kept row is free."
    )

st.divider()

# --- cost -----------------------------------------------------------------

st.subheader("Cost")
spend = total_spend()
if not COST_LOG.exists():
    empty_state("No LLM calls have been logged yet, so there is no cost to report.")
else:
    st.metric("Total logged spend", f"${spend:.4f}")
    st.caption(f"Every call is logged to `{COST_LOG}` with tokens and latency.")

st.divider()

# --- what is not measured -------------------------------------------------

st.subheader("Not yet measured")
st.markdown(
    """
These are wired and tested but have produced no numbers, because the inputs
they need do not exist yet:

- **Ragas groundedness / faithfulness** (W5.7) — needs generated reports, which need an API key.
- **Human rubric scores** (W5.8) — needs a fixed output set drawn from saved runs.
- **Citation correctness** (W4.8) — implemented and unit-tested; needs a real generation run.
- **Insight tree** (W3.6) — needs Tier-3 curation.

Publishing placeholder numbers for any of these would be the exact failure
this project is built to avoid.
"""
)

honesty_footer()
