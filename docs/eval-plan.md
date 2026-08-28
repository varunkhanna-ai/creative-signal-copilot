# Evaluation plan

## Headline: no numbers have been produced

Every metric below is **wired, unit-tested, and unrun**. The harness refuses to print results it cannot stand behind, and the eval dashboard renders "not yet measured" rather than a zero.

Two inputs are missing, both tracked in [`decision-log.md`](decision-log.md) under BLOCKERS:

- **B1/B2 — the corpus.** 9 unique synthetic ads. A top-5 query returns more than half of it, so Recall@5 and Precision@5 are degenerate and the semantic-vs-hybrid comparison cannot separate its conditions.
- **W2.6 — the golden set.** Not built. Labeling relevance against 9 template ads would produce a set that measures nothing.

`make eval` runs today and exits with an explanation. That is the intended behavior, not an unfinished state.

## Targets (§11)

| Metric | Target | Status |
|---|---|---|
| Recall@5 | 0.70 | not measured |
| Precision@5 | 0.60 | not measured |
| Citation correctness | 0.95 | not measured |
| Groundedness (Ragas) | 0.80 | not measured |
| Human rubric (6 dimensions) | — | not scored |

## Retrieval metrics — hand-rolled, and why

Recall@5 and Precision@5 are ~30 lines total. Keeping them hand-rolled means every formula is explainable in an interview, including the two decisions that actually matter:

**Counting unit is the creative ID, deduplicated** (Entry #11). A creative indexed under both its card and its analyst summary counts **once**. The golden set labels creatives, not representations — a human answering "is this ad relevant?" has no view of the index's internals. Counting representations would make the metric depend on how many ways we happen to index a record, and would let the two-representation design inflate its score against the baseline it is compared to. The comparison is only fair if both sides are scored in the same units.

**Precision divides by results actually returned, not by a literal `k`.** On a small corpus a query can return fewer than 5. Dividing by 5 would penalize the retriever for the corpus's size rather than its ranking.

**Citation correctness** = fraction of cited IDs that were actually retrieved. This is the hallucinated-citation metric: a concept citing an ID it was never given is the precise failure the honesty rule forbids. An uncited output scores 0.0 — an uncited concept is not a well-grounded one. The same rule runs as a *gate* at generation time (the agent drops such concepts), so this metric measures how often the gate has to fire.

## Three conditions, always compared

`make eval` runs the golden set against **keyword-only** (the W1.11 naive baseline), **semantic-only**, and **hybrid**. Reporting hybrid alone would assert an improvement rather than demonstrate one.

`SEMANTIC_WEIGHT` is a single named constant (currently 0.5, an untuned honest default) so it can be swept the moment a golden set exists.

## Generation metrics

**Ragas** covers faithfulness and answer relevancy over concepts drawn from the `runs` table by `run_id`. Scope split is deliberate: Ragas for generation, hand-rolled for retrieval. DeepEval and Ragas overlap; one framework is enough.

**Human rubric** ([`rubric.md`](../src/creativesignal/eval/rubric.md)) — six dimensions with written 1/3/5 anchors so raters share a scale. The fixed output set is drawn by `run_id`, so every scorer rates identical outputs and results stay re-traceable. Report per-dimension means with the scorer count; never blend into one "quality" score, since grounding and novelty pull against each other by design.

## Failure reading (L1) — the part that matters more than the metric

After every eval run: open the 10 worst retrieval failures and categorize each as **wrong filter parse / vocabulary mismatch / label error / genuinely ambiguous query**. One paragraph in the decision log. The categories tell you what to fix; the aggregate number does not.

`run_eval.py` prints the worst failures with their missed IDs to make this cheap.

This habit already paid off before any eval ran. Applying it to *ingest* — reading the actual rows rather than the row count — is what exposed a 17% false-positive rate in the vertical filter and near-total overlap between two supposedly independent datasets (Entry #7). The row count looked fine at 24; the rows did not.

## Guards against reporting noise

The harness refuses rather than reporting a number that would mislead:

| Guard | Threshold | Rationale |
|---|---|---|
| Golden-set floor | 10 queries | Below it, a mean is noise; `run_eval` warns loudly |
| Ragas sample floor | 5 samples | Same |
| LR training floor | 20 rows, 2 per class | Refuses to fit; no accuracy figure at all |
| Tree training floor | 30 rows, 2 classes | Refuses to fit |

Each raises with a message naming the blocker and the task that would clear it.

## Uncalibrated values — flagged, not hidden

Three constants are defensible priors, **not** fitted values. Each carries the procedure for setting it properly once data exists:

| Constant | Current | Set it by |
|---|---|---|
| Escalation confidence (Entry #9) | 0.70 | Read the W1.8 threshold table; take the lowest escalation rate clearing the accuracy target |
| Proxy buckets (Entry #5) | 90 days / 5 variants | Check class balance on real Tier-3; rebalance if one bucket dominates |
| Semantic similarity floor (Entry #20) | none | Sweep alongside `SEMANTIC_WEIGHT` once the golden set exists |

Publishing a number derived from any of these today would be presenting a guess as a measurement.

## Cost

Every LLM call is logged to `eval/cost_log.csv` with task, model, tokens, cost, and latency (L2). This makes the Job A claim a measured number rather than an estimate — specifically, the escalation rate is the cost lever: every escalated row is an LLM call, every row the classifier keeps is free.
