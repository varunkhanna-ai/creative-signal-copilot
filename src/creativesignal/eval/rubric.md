# Human evaluation rubric (W5.8)

Six dimensions, scored **1–5**. Every dimension has written anchors for 1, 3, and 5 so raters share a scale — without them, "4" means something different to every scorer and the averages are not comparable.

## How to run this

1. Pick a fixed set of outputs **by `run_id`** from the `runs` table. Stable IDs mean every scorer rates identical outputs and any result stays re-traceable later.
2. Give each scorer the same runs in the same order. Do not tell them which prompt or model version produced which output.
3. Record scores in `eval/results/human_eval.csv`, with these columns and nothing else:

   ```csv
   run_id,scorer,dimension,score,note
   ```

   No scores in this repository were produced by a model, and no example row is supplied — scoring is a human rater's job, and a model scoring its own system's outputs would measure nothing.
4. Report **per-dimension means with the number of scorers**, never a single blended "quality" score — a blended score hides that grounding and novelty pull in opposite directions.

Target: 3–5 scorers. Below 3, report individual scores rather than a mean.

---

## 1. Relevance — does the output address the brief?

- **1** — Ignores the brief. Wrong product category or wrong audience entirely.
- **3** — Addresses the brief broadly but generically; would fit many briefs equally well.
- **5** — Directly answers this brief, including its audience and tone constraints.

## 2. Specificity — is it concrete enough to act on?

- **1** — Generic marketing language that could describe any product ("elevate your routine").
- **3** — Some concrete detail, but a designer or copywriter would still have to invent the substance.
- **5** — Names specific hooks, framings, and copy angles a team could execute from directly.

## 3. Grounding — is every claim supported by its citation?

- **1** — Claims with no citation at all, or citations to creative IDs that were not retrieved.
- **3** — Cited, but the citation only partially supports the claim — the source is related without actually containing what is asserted.
- **5** — Every claim is fully supported by the specific creative it cites, and the citation is checkable.

*This is the dimension that maps to the honesty rule. Score it strictly: "sounds plausible" is not grounding.*

## 4. Actionability — could a team use this on Monday?

- **1** — No clear next step; reads as analysis with no output.
- **3** — Useful direction, but needs substantial interpretation before anyone could brief it.
- **5** — A creative team could take this into production with minor edits.

## 5. Brand safety — would this pass a real review?

- **1** — Contains claims that would be rejected by an ad platform or a legal team (unsupported efficacy, prohibited targeting).
- **3** — Nothing disqualifying, but at least one line a cautious reviewer would want changed.
- **5** — Clean. No regulated claims, no false urgency, no targeting language.

*Score this independently of what the automated Reviewer flagged. Scorer-vs-reviewer disagreement is a finding worth having, not noise — it is the measurement of whether the reviewer's rules match human judgment.*

## 6. Novelty — does it go beyond restating the evidence?

- **1** — Paraphrases a retrieved ad almost verbatim.
- **3** — Recombines observed patterns without adding an idea.
- **5** — Draws a non-obvious connection across examples that a human would not have reached by reading them individually.

*Novelty is in tension with grounding by design. An output scoring 5 on both is genuinely good; a 5 on novelty with a 2 on grounding is the model inventing. Record both rather than averaging them away.*

---

## Known bias to control for

Scorers who know the project's thesis will over-reward outputs that use hedged, descriptive language. **Do not brief scorers on the honesty rule before they score** — score grounding on whether claims are actually supported, not on whether the output sounds appropriately cautious.

## Status

**Not yet run** — needs generated runs, which need an API key (docs/decision-log.md B3) and a corpus worth generating from (B2). The rubric is finalized; the scoring pass is outstanding.
