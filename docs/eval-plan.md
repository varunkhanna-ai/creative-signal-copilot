# Evaluation plan

## Headline: retrieval metrics are blocked; generation metrics are real

The corpus is no longer the constraint — Tier-3 curation landed (95 real rows, 104 creatives total, decision-log Entry #22/#23). **The retrieval golden set (W2.6) does not exist**, and that is the one remaining blocker on Recall@5/Precision@5. No golden set was approximated from the corpus itself to fill the gap — that would be circular, since the corpus is exactly what retrieval is being measured against.

Everything that does *not* require a golden set has been run for real, against the live API and the real 104-row corpus, and the numbers below are what actually came back — not estimates.

## Targets (§11)

| Metric | Target | Status | Measured |
|---|---|---|---|
| Recall@5 | 0.70 | **blocked on B5** — no golden set | — |
| Precision@5 | 0.60 | **blocked on B5** — no golden set | — |
| Citation correctness | 0.95 | **measured** | **1.000**, n=15 concepts, post-gate (Entry #29) |
| Citation correctness (pre-gate) | — | measured | **1.000**, n=9, 0 dropped by the self-check gate (Entry #29) |
| Ragas answer relevancy | — | measured | **0.573–0.627** across two runs, n=15 (Entry #30) |
| Ragas faithfulness | 0.80 | **measured, but not usable** | 0–3 of 15 samples scored per run — parser incompatibility, see Entry #30 |
| Planted-violation reviewer test | pass/fail | **measured** | passes, deterministic (`test_planted_prohibited_claim_is_flagged`) |
| Human rubric (6 dimensions) | — | not scored | scoring is a human's job (Entry #21) |

## Retrieval metrics — hand-rolled, and why

Recall@5 and Precision@5 are ~30 lines total. Keeping them hand-rolled means every formula is explainable in an interview, including the two decisions that actually matter:

**Counting unit is the creative ID, deduplicated** (Entry #11). A creative indexed under both its card and its analyst summary counts **once**. The golden set labels creatives, not representations — a human answering "is this ad relevant?" has no view of the index's internals. Counting representations would make the metric depend on how many ways we happen to index a record, and would let the two-representation design inflate its score against the baseline it is compared to. The comparison is only fair if both sides are scored in the same units.

**Precision divides by results actually returned, not by a literal `k`.** On a small corpus a query can return fewer than 5. Dividing by 5 would penalize the retriever for the corpus's size rather than its ranking.

**Citation correctness** = fraction of cited IDs that were actually retrieved. This is the hallucinated-citation metric: a concept citing an ID it was never given is the precise failure the honesty rule forbids. An uncited output scores 0.0 — an uncited concept is not a well-grounded one. The same rule runs as a *gate* at generation time (the agent drops such concepts), so this metric measures how often the gate has to fire.

## Three conditions, always compared

`make eval` runs the golden set against **keyword-only** (the W1.11 naive baseline), **semantic-only**, and **hybrid**. Reporting hybrid alone would assert an improvement rather than demonstrate one. This is fully wired against the real 104-creative corpus and the real 208-document Chroma index — the only missing input is the golden set itself (B5).

`SEMANTIC_WEIGHT` is a single named constant (currently 0.5, an untuned honest default) so it can be swept the moment a golden set exists.

## Generation metrics — real results, with real caveats

**Ragas** covers faithfulness and answer relevancy over the 15 concepts in the `runs` table from six real end-to-end generation runs. Scope split is deliberate: Ragas for generation, hand-rolled for retrieval. DeepEval and Ragas overlap; one framework is enough.

Getting a real number out of Ragas required fixing two bugs first (Entry #30): Ragas defaults to OpenAI as its judge LLM, which would need a second vendor key the project deliberately doesn't have — fixed by wrapping the project's own Claude client via `langchain-anthropic`. And `temperature` is deprecated on Sonnet 5 (the same error `llm.py` hit directly, Entry #29), injected two layers deep inside Ragas's own call chain, so the fix required overriding `agenerate_text` itself rather than a constructor argument.

**Result, with the honest caveat:** `answer_relevancy` scored reliably — 0.573 and 0.627 across two independent runs, all 15 samples. `faithfulness` did **not** — its NLI-statement prompt fails to parse Claude's output on most calls (a real parser-compatibility gap between this ragas version and Claude, diagnosed but not fixed), scoring only 0–3 of 15 samples per run. `ragas_eval.py` reports `n_scored` per metric precisely because of this: a mean that silently dropped 12 of 15 samples would misstate its own support, the same failure mode the golden-set floor below exists to prevent.

**Human rubric** ([`rubric.md`](../src/creativesignal/eval/rubric.md)) — six dimensions with written 1/3/5 anchors so raters share a scale, headers-only CSV template with no example scores (a model scoring its own system's outputs measures nothing, Entry #21). The fixed output set is drawn by `run_id` from the six real persisted runs, so every scorer rates identical outputs and results stay re-traceable. Not yet run — scoring is a human's job. Report per-dimension means with the scorer count; never blend into one "quality" score, since grounding and novelty pull against each other by design.

## Failure reading (L1) — the part that matters more than the metric

After every eval run: open the 10 worst retrieval failures and categorize each as **wrong filter parse / vocabulary mismatch / label error / genuinely ambiguous query**. One paragraph in the decision log. The categories tell you what to fix; the aggregate number does not.

`run_eval.py` prints the worst failures with their missed IDs to make this cheap.

This habit already paid off before any eval ran. Applying it to *ingest* — reading the actual rows rather than the row count — is what exposed a 17% false-positive rate in the vertical filter and near-total overlap between two supposedly independent datasets (Entry #7). The row count looked fine at 24; the rows did not.

## Guards against reporting noise

The harness refuses rather than reporting a number that would mislead:

| Guard | Threshold | Rationale | Status |
|---|---|---|---|
| Golden-set floor | 10 queries | Below it, a mean is noise; `run_eval` warns loudly | Still applies — golden set is 0 queries (B5) |
| Ragas sample floor | 5 samples | Same | Cleared — 15 real samples; `n_scored` reported per metric (Entry #30) |
| LR training floor | 20 rows, 2 per class | Refuses to fit; no accuracy figure at all | Cleared — trained on 98 real rows, one class (`authority_expert`, n=1) dropped rather than faked (Entry #25) |
| Tree training floor | 30 rows, 2 classes | Refuses to fit | Cleared — trained on 95 real Tier-3 rows, 3 balanced buckets (Entry #27) |

Each raises with a message naming the blocker and the task that would clear it.

## Values that were placeholders, now recalibrated against real data

Three constants were flagged as defensible-but-unfitted priors before real data existed. All three have now been checked against it (or, in one case, found to need a different fix entirely):

| Constant | Was | Recalibrated to | Basis |
|---|---|---|---|
| Escalation confidence (Entry #9 → #26) | 0.70 (placeholder) | **0.35** | Real out-of-fold threshold table: 0.70 escalated 93–98% of rows, collapsing the two-stage design. 0.35 is the lowest threshold clearing 95%+ accuracy-on-kept on both axes |
| Proxy buckets (Entry #5 → #23) | 90 days / 5 variants | **10 / 25 days, `variant_count` dropped** | `variant_count` is a constant 20 across all 95 real rows — zero information, and it single-handedly forced 95/95 into `high` under the old rule. Recalibrated on `days_active` alone against its real tertiles (8.0, 22.7 days), giving a balanced 36/31/28 split |
| Semantic similarity floor (Entry #20) | none | **still none** | Real off-topic-vs-relevant cosine gap is only ~0.08 (0.67 vs 0.59) — a floor set in that band without a golden set would risk silently returning nothing for real queries. Still deferred to when B5 clears |

The base-rate model quality behind the escalation threshold is now a real number too: hook_type **90.5%** out-of-fold accuracy, tone **79.6%**, n=95–98 (Entry #26).

## Cost

Every LLM call is logged to `eval/cost_log.csv` with task, model, tokens, cost, and latency (L2). This makes the Job A claim a measured number rather than an estimate — specifically, the escalation rate is the cost lever: every escalated row is an LLM call, every row the classifier keeps is free.

**Actual spend to date, read from the log, not summed by hand:** **$0.5350** across 98 bootstrap labels, 5 escalations (out of 98 rows, a 5.1% in-sample rate — the real out-of-fold estimate is closer to 40%, driven by the weaker tone axis; see Entry #26 for why the two numbers differ), 104 analyst summaries, and 6 end-to-end generation runs.

## What is left, precisely

One blocker, not several: **B5, the golden set (W2.6)**. Everything downstream of it — Recall@5/Precision@5, semantic-vs-hybrid, the similarity-floor sweep, the retrieval-side rows of the README results table — is wired against real data and waiting only on that. Nothing else in this document is still hypothetical.
