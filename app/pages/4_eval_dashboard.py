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
from shared import empty_state, honesty_footer, page_header

from creativesignal.annotate.escalate import CONFIDENCE_THRESHOLD, escalation_stats_from_db
from creativesignal.eval.metrics import citation_correctness, load_golden_set
from creativesignal.llm import COST_LOG, total_spend
from creativesignal.runs import list_runs

st.set_page_config(page_title="Eval — CreativeSignal", layout="wide")

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


def latest_ragas_results() -> dict | None:
    path = RESULTS_DIR / "ragas_eval.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


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
        "No retrieval eval has been run. The corpus is no longer the "
        "constraint (104 creatives, 95 with real Meta Ad Library provenance) "
        "— the golden set (W2.6, 20+ hand-labeled queries) is the one input "
        "still missing. This panel deliberately shows nothing rather than a "
        "misleading zero. See docs/decision-log.md B5."
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

# --- generation -------------------------------------------------------------

st.subheader("Generation")

runs = list_runs(limit=25)
concepts_with_context = [
    (run, concept) for run in runs for concept in run.concepts
]

if not concepts_with_context:
    empty_state(
        "No generation runs with concepts exist yet. Citation correctness is "
        "implemented and unit-tested; it needs a real run to measure."
    )
else:
    scores = [
        citation_correctness(concept.cited_creative_ids, run.retrieved_creative_ids)
        for run, concept in concepts_with_context
    ]
    mean_score = sum(scores) / len(scores)
    columns = st.columns(2)
    columns[0].metric(
        "Citation correctness",
        f"{mean_score:.3f}",
        delta=f"{mean_score - TARGETS['citation_correctness']:+.3f} vs target",
    )
    columns[1].metric("Concepts scored", len(scores))
    st.caption(
        f"Across {len(runs)} persisted runs. Fraction of cited creative IDs "
        "that were actually retrieved — a concept citing evidence it was "
        "never given does not ship (the agent's self-check gate), so this "
        "number reflects how often that gate would have had to fire."
    )

ragas_results = latest_ragas_results()
if ragas_results is None:
    empty_state(
        "No Ragas evaluation has been run yet. Run `python -m "
        "creativesignal.eval.ragas_eval` — it needs generated runs and an "
        "API key."
    )
else:
    st.caption(
        f"Ragas, judged by Claude (not OpenAI — see decision-log Entry #30), "
        f"over {ragas_results['n_samples']} concepts from "
        f"{len(ragas_results['run_ids'])} runs."
    )
    n_scored = ragas_results.get("n_scored", {})
    columns = st.columns(2)
    relevancy = ragas_results["scores"].get("answer_relevancy")
    if relevancy is not None and not (isinstance(relevancy, float) and relevancy != relevancy):
        columns[0].metric(
            "Answer relevancy",
            f"{relevancy:.3f}",
            help=f"Scored on {n_scored.get('answer_relevancy', '?')} of "
                 f"{ragas_results['n_samples']} samples",
        )
    faithfulness = ragas_results["scores"].get("faithfulness")
    scored_n = n_scored.get("faithfulness", 0)
    if faithfulness is None or (isinstance(faithfulness, float) and faithfulness != faithfulness):
        columns[1].metric("Faithfulness", "unusable", delta=f"{scored_n} of {ragas_results['n_samples']} scored", delta_color="off")
    else:
        columns[1].metric(
            "Faithfulness",
            f"{faithfulness:.3f}",
            delta=f"{faithfulness - TARGETS['groundedness']:+.3f} vs target ({scored_n} of {ragas_results['n_samples']} scored)",
        )
    st.caption(
        "Faithfulness's NLI-statement prompt fails to parse Claude's output "
        "on most calls in this ragas version — diagnosed, not fixed. The "
        "score above (if any) is a mean over only the samples that parsed; "
        "see docs/decision-log.md Entry #30."
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
- **Recall@5 / Precision@5, semantic-vs-hybrid** (W2.8) — blocked on the golden set (W2.6, human), not on the corpus. See decision-log B5.
- **Ragas faithfulness** (W5.7) — run, but not usable: a parser incompatibility between this ragas version and Claude's output scores only a few of every 15 samples. Reported above as broken, not hidden. See decision-log Entry #30.
- **Human rubric scores** (W5.8) — the rubric and its fixed output set (drawn from the real persisted runs above) exist; scoring is a human's job and hasn't happened yet.

Publishing a placeholder number for any of these would be the exact failure
this project is built to avoid — each is reported as exactly what it is,
including "measured, but not usable" where that's the honest state.
"""
)

honesty_footer()
