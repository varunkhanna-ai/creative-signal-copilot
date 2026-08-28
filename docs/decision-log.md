# CreativeSignal — Decision Log

## BLOCKERS — NEEDS HUMAN REVIEW

*Running note. Each entry states what is blocked, what unblocks it, and what was built anyway so the blocker is the only remaining gap.*

### B1 — Tier-3 corpus does not exist (blocks W3.6, all eval numbers)

`docs/tier3_review_sheet.xlsx` was reported as existing with only `category` / `rights_note` blank. It does not exist — not in this worktree, not in `CAPSTONE/`, not in `creativesignal-kc/`, not anywhere under Desktop or Downloads. The only related file is `~/Downloads/tier3_curation_template.xlsx`: correct 14-column header, exactly **one** row (a CeraVe example whose `notes` column reads "Example row — replace with real curated data. Delete before use").

W0.3 was never done. Consequences:

- **W1.4** target is ~300 rows (all Tier-3 + a Tier-2 sample). Tier-3 contributes 0. Actual load is Tier-2 only — see B2.
- **W3.6 (insight tree) cannot run.** Per F1 the tree trains only on Tier-3; with no rows there is no `proxy_bucket` label column at all. Code is built and unit-tested against a synthetic frame; it has never been trained on real data.
- **Provenance fields are unpopulated corpus-wide.** Tier-3 is the only tier carrying `ad_library_url`, real `rights_note`, and the F1 proxy fields (`days_active`, `variant_count`, `proxy_bucket`).

**Not worked around deliberately.** Generating 100–200 plausible skincare records would fabricate advertisers, ad-library URLs, and observation dates in a project whose stated spine is "every insight is traceable to examples," and every downstream citation, tree rule, and eval number would then trace to invented data. The honesty rule makes this the one gap that must stay visible rather than be filled.

**Unblocked by:** the human doing W0.3 (2h in plan) and saving to `data/raw/tier3_meta_sample.csv`. `ingest/load_tier3.py` is built, validates against the template's 14 columns, and will pick the file up with no code change.

### B2 — Tier-2 yields **9 unique** skincare ads, not ~300 (blocks every eval number, and W1.8)

Measured, then re-measured after two filter bugs were fixed (Entry #7). The honest number is **9**:

| Stage | Rows |
|---|---|
| Raw keyword match across both datasets | 24 |
| After vetoing non-skincare products (clothes irons, garment steamers, hair serum matched on "wrinkle"/"serum") | 16 |
| After cross-dataset dedupe (the two datasets overlap almost entirely) | **9** |

The nine: anti-aging serum, eye cream, sunscreen, body scrub, face scrub, moisturizing cream, facial cleanser, exfoliating scrub, CC cream.

This is worse than first reported and blocks more than eval:

- **Retrieval metrics are degenerate.** Recall@5 / Precision@5 over a 9-document corpus means a single query retrieves more than half the corpus. W2.8's semantic-vs-hybrid comparison cannot separate the two conditions at this size. **No eval run has been executed and no eval numbers committed.** `make eval` is wired and will run; it is deliberately unrun rather than reported on a corpus that would make the output meaningless.
- **W1.8 LR training is not viable.** Nine rows across 6–8 `hook_type` classes averages roughly one example per class. There is no train/test split worth making. The classical annotator is built and unit-tested on synthetic data; it has not been trained on the real corpus.
- **The corpus has near-zero stylistic variance.** All nine follow one generated template — "Experience X! Perfect for Y. Limited stock - Z." Every single row contains "Limited stock," so the W4.5 false-scarcity check would flag 100% of the corpus. A `tone`/`hook_type` classifier trained here would learn one template, not a taxonomy.

**Unblocked by:** B1 (Tier-3 lands → ~150–250 real, stylistically varied, provenance-rich rows) plus W2.6 golden set (Human, 20 queries × 3–5 relevant IDs). Both are prerequisites to any number entering `docs/eval-plan.md` or the README results table.

### B3 — `ANTHROPIC_API_KEY` not present

Reported as added to `.env`; no `.env` exists in `creativesignal-cc/`, `CAPSTONE/`, or `creativesignal-kc/` as of this run. `.env` files in sibling projects (`Agent Demo`, `ladder-*`) were left unread — harvesting another project's credential is not an autonomous call.

Blocks *execution* of every LLM path: W1.6 bootstrap labeling → therefore W1.8 LR training and W1.10 escalation (both need bootstrap labels), W2.3 analyst summaries, W3.3 analyst agent, W4.3 concepts, W4.5 reviewer. Code for these is built; none has been executed against the live API.

**Unblocked by:** `echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env` in the repo root (already gitignored).

### B4 — Tier-1 (AdImageNet) is gated (minor, off critical path)

`PeterBrendan/AdImageNet` now returns `DatasetNotFoundError: gated dataset ... must be authenticated`. License reads **MIT** on the card, but the files require an HF token with access granted. Tier-1 is not on the critical path (image corpus, no copy); `load_tier1.py` is built and raises a clear message pointing at this entry.

**Unblocked by:** accepting the gate on the HF dataset page + `huggingface-cli login`.

---

## Entry #1 — Vertical: Skincare (W0.2)

**Decision:** Confirmed skincare as the vertical, per the default in `implementation.md` §0.1.

**Rationale:** Densest coverage in the Meta Ad Library among the three candidates considered (skincare, fitness apparel, meal-kit); both Tier-2 ad-copy datasets contain beauty/skincare rows; skincare's regulated efficacy claims ("clinically proven," "reduces wrinkles") make the Reviewer agent genuinely load-bearing rather than decorative — a real policy-risk surface exists to catch.

**Alternatives considered:** Fitness apparel, meal-kit — both were viable per the strategy doc's own framing (the vertical is a filter value and curation choice, not an architectural one), but skincare's regulatory density gives the Reviewer agent a sharper demo story.

**Status:** Locked. Nothing downstream changes except dataset filters and example queries if revisited.

## Entry #2 — Stretch goal: `visual_direction` field on Concept (not scheduled)

**Idea:** Add a written "visual direction" field to each generated Concept — composition, mood, color palette, product placement, referencing patterns from retrieved evidence. A text prompt/brief a human could hand to a designer or image-gen tool, not an actual generated image.

**Why this version, not actual image generation:** Text-only stays inside existing constraints — no new vendor key (`ANTHROPIC_API_KEY` remains the only secret), no new dependency, same Sonnet call that already generates the concept. Actual image generation would require a second vendor API key, directly violating the DECIDED "no extra vendor API keys" rule, and adds a content-moderation/cost/quality failure surface that cuts against "explainability beats sophistication."

**Where it fits the plan:** "Image drafts" is already named in the cut order (fine-tune → A2A → image drafts → MCP) as the third thing cut if time runs short — this entry just defines what that stretch item would concretely mean if pursued, following the same kill-switch logic already used for fine-tuning (only enters if Weeks 1–4 bank surplus, exits after a capped time regardless).

**Status:** Not scheduled. Revisit at the W4.2 walkthrough (Concept schema / "what must the evidence contain") — decide there whether to add `visual_direction: str` or defer for good, based on actual time banked by Week 4.

## Entry #3 — `creatives` vs. `annotations` split rule (W1.2)

**Decision:** `annotations` holds only fields a model/classifier made a judgment call on (`hook_type`, `tone`, `confidence`, `annotator`). Everything deterministically computed from observed facts — `days_active`, `proxy_bucket`, `variant_count` — lives in `creatives` alongside the raw fields (`start_date`, etc.) they're calculated from, even though they're not directly observed.

**Rationale:** The dividing line is "did a model exercise judgment," not "was this computed." Simple arithmetic/rule-based derivation (subtraction, threshold buckets) carries no risk of being wrong in the way a model's classification can be — it's fully deterministic and reproducible from the source fields. Keeping it in `creatives` also means the F1 proxy fields don't need an `annotator`/`confidence` pair they don't actually have a use for.

**Status:** Locked for schema implementation (W1.3).

## Entry #4 — Cloud Agent false-completion pattern (W1.1)

**What happened:** During W1.1 (repo scaffold), a Kilo Cloud Agent session reported task completion three times in a row where the claimed fix had not actually landed — twice claiming a fix was applied when `git log` showed no new commit at all, and the underlying files were unchanged from the original scaffold. Only the fourth attempt (a fresh session) actually committed and pushed real changes, verified against `git log` and direct file contents.

**Lesson:** A coding agent's self-reported "done" is not evidence of anything — only `git log` (a new commit exists) and direct inspection of file contents are. This applies to both tools, not just Cloud Agents specifically, but showed up here because unattended/overnight runs remove the chance to catch it in the moment.

**Process change going forward:** After any task handoff, verify via `git log --oneline` (confirm a new commit landed) and `cat`/`find` on the actual changed files — never accept a chat summary of what was done as sufficient. If a session reports completion but git shows no new commit, don't re-prompt the same session more than once — start a fresh session, since a session stuck in a false-completion loop is unlikely to self-correct.

**Status:** Standing practice for all remaining tasks.

## Entry #5 — F1 proxy-bucket thresholds: fixed, not percentile (W1.4)

**Decision:** `proxy_bucket` is assigned by fixed thresholds — **high** if `days_active >= 90` *or* `variant_count >= 5`; **low** if `days_active < 30` *and* `variant_count <= 1`; **mid** otherwise.

**Rationale — why fixed and not tertiles of the corpus:** Entry #3 puts `proxy_bucket` in `creatives` on the grounds that it is *deterministic from its source fields*. Percentile bucketing would break exactly that property: a record's bucket would change when other records are added, making the column a function of the corpus rather than of the ad, and silently invalidating any tree trained before the last ingest. Fixed thresholds keep the field reproducible from `start_date` / `date_observed` / `variant_count` alone.

**Why OR for high and AND for low:** the two signals are independent evidence of the same thing (advertiser keeps paying). Either a long run or heavy variation is sufficient to say "sustained investment"; it takes both a short run and no variation to say "no evidence of sustained investment."

**Calibration status — open.** These numbers are not calibrated against real data, because there is no Tier-3 data yet (B1). 90 days and 5 variants are plausible industry-standard reference points, not fitted values. **When W0.3 lands, check the resulting class balance before training the W3.6 tree** — if one bucket holds most of the corpus, the tree will be uninformative and the thresholds should be re-set to roughly balance the three classes, with the change logged here.

**Honesty framing (unchanged):** this is a spend-persistence signal, not a performance measurement. `compute_proxy_bucket`'s docstring carries that sentence so it stays attached to the code that produces the label.

## Entry #6 — Dependency cascade blocking the whole test suite (W1.4, debugging)

**What happened:** `pytest` could not collect *any* test — it died during startup, before running a single case. Root cause was two levels down: `arize-phoenix` 8.0.0 registers a `pytest11` entry-point plugin, so `import phoenix` happens at pytest startup regardless of whether a test touches tracing. That import failed twice over, on two *unpinned transitive* dependencies: `arize-phoenix-evals` 3.3.0 no longer exposes `phoenix.evals.models`, and `uvicorn` 0.52.1 no longer exposes `uvicorn.config.LoopSetupType`.

**Fix:** pinned `arize-phoenix-evals==0.20.8` and `uvicorn==0.34.3` in `pyproject.toml`, with a comment recording why.

**Lesson worth keeping:** the earlier "pin all dependencies to exact versions" commit pinned only *direct* dependencies. Transitive dependencies stayed floating, so a project that looked fully pinned was still able to break on an upstream release. It surfaced as "the test suite is broken" rather than "tracing is broken," because a pytest plugin makes one library's import health everyone's problem.

**Status:** Fixed. Consider a lockfile (`uv lock` / `pip freeze` snapshot) at W6.1 so the grader's install is reproducible.

## Entry #7 — Tier-2 filter precision and cross-dataset dedupe (W1.4)

**What the data showed.** Printing all 24 initially-matched rows surfaced two bugs that a row count alone would have hidden:

1. **False positives from body-copy keyword overlap.** "Steam Iron," "Clothes Iron," and "Garment Steamer" matched on **wrinkle** — as in wrinkle-free *shirts*. "Hair Serum" matched on **serum**. Four of 24 matches were not skincare: a 17% error rate in the vertical filter, and every one of them would have become retrievable "evidence" for a skincare brief.
2. **Near-total overlap between the two Tier-2 datasets.** `t2_smangrul_0343` and `t2_jaykin_0312` are byte-identical, as are Steam Iron, Garment Steamer, Facial Cleanser, Moisturizing Cream, Anti-Aging Serum, Sunscreen, Eye Cream, Body Scrub, and Face Scrub. `jaykin01/advertisement-copy` and `smangrul/ad-copy-generation` are not independent sources.

**Decisions.**

- **Product-name veto** (`NON_SKINCARE_PRODUCTS`), checked before the keyword match. The product name is the category signal; the body copy is where misleading overlap lives, so the veto reads the product name only. Ordering matters and is asserted in tests.
- **Cross-dataset dedupe on normalized body copy**, first occurrence wins. Rationale beyond tidiness: a duplicate inflates every retrieval metric (the same text matching twice looks like two relevant results) and would let an ad be cited as independent evidence for itself — a direct hit on "every insight is traceable to examples," since the two citations would trace to one example.
- A creative with **no body copy is dropped**: nothing to retrieve on.

**Consequence, recorded rather than smoothed over:** the usable Tier-2 corpus is **9 unique ads**, not the 24 first reported or the ~300 the plan assumed. B2 is updated with the corrected figure and the extra tasks it blocks (W1.8 LR training is no longer viable on real data). Finding this now rather than at W2.8 is the reason the eval numbers were not going to be trustworthy either way.

**Lesson:** the row count looked fine at 24. Reading the actual rows is what surfaced both bugs — the L1 "failure reading" habit the plan schedules for eval runs applies just as well to ingest.

## Entry #8 — Frozen `hook_type` / `tone` taxonomies (W1.5)

**Decision.** Seven hook types — `problem_solution`, `benefit_promise`, `social_proof`, `authority_expert`, `curiosity_question`, `offer_led`, `ingredient_led`. Six tones — `clinical`, `aspirational`, `warm_reassuring`, `playful`, `urgent`, `minimal_matter_of_fact`. Frozen in `annotate/taxonomy.py`, with a change-detector test.

**The design rule that generated them:** `hook_type` is *the rhetorical device that opens the ad*; `tone` is *the register it speaks in*. Keeping the axes orthogonal is what makes the pair informative — if `tone` had included "clinical-authority" it would collapse into `authority_expert` and the second label would add nothing. A test asserts the two sets don't overlap.

**Why these seven hooks:** the first five are the standard direct-response openers and are vertical-neutral. The last two are skincare-specific and earn their slots from the vertical decision (Entry #1): `offer_led` because discount-led beauty advertising is a distinct and very common mode, and `ingredient_led` because "reason to believe = named active" is *the* skincare-specific convention (retinol, niacinamide, SPF) and is exactly the surface where the Reviewer's efficacy-claim check does its work.

**Why `unclear` is a label but not in the taxonomy:** the bootstrap LLM (W1.6) can return `unclear`. A forced wrong label enters the LR training set as silent noise and is unrecoverable afterwards; an explicit `unclear` is visible, countable, and can be routed to human review. It is deliberately not a member of `HOOK_TYPES`/`TONE_LABELS` so it can never be predicted as a real class.

**Calibration caveat (B2).** These label sets were designed against skincare advertising conventions, **not** fitted to the current corpus — the nine available Tier-2 ads are one generated template and would support perhaps two of the thirteen labels. That is the right order of operations (the taxonomy should describe the domain, not the sample), but it means **label coverage must be re-checked when Tier-3 lands**. If a label draws near-zero real examples it should be merged or cut *then* — which requires re-running W1.6 onward, per the freeze rule. Deciding this now on nine template rows would be fitting to noise.

## Entry #9 — Escalation confidence threshold: 0.70 (W1.9)

**Decision:** `CONFIDENCE_THRESHOLD = 0.70` in `annotate/escalate.py`. Rows where *either* axis predicts below 0.70 escalate to Haiku.

**The tradeoff being made.** This is the Job A PM story in one number. Lower threshold → fewer LLM calls, lower cost, more wrong labels shipped by the LR. Higher threshold → more LLM calls, higher cost, fewer wrong labels. The quantity to optimize is not raw LR accuracy but **accuracy on the rows the LR keeps**, since everything below the line gets relabeled anyway — which is why `report.py`'s threshold table reports `acc@kept` and `escal%` side by side rather than a single accuracy figure.

**Why 0.70 specifically, and the honest caveat.** 0.70 is the standard starting point for a multi-class softmax over ~6–7 classes: comfortably above the ~0.14 uniform-random baseline, below the point where a well-separated class gets escalated for no reason. **It is not fitted to data** — it cannot be, because there is no seed set to fit against (B2/B3). The plan has W1.9 read the threshold off the W1.8 P/R table; that table needs the bootstrap to have run, which needs the API key and a corpus larger than nine template rows.

**What must happen when data exists:** run `python -m creativesignal.annotate.classical`, read the printed threshold table, and pick the row where `acc@kept` clears the §11 target at the lowest `escal%`. If 0.70 is not that row, change the constant and amend this entry with the table. Treat the current value as a placeholder with a defensible prior, not a measured result.

**Design choices that survive recalibration:**
- **Per-row, not per-axis, escalation.** If either axis is unsure the whole row goes to the LLM. Splitting would mean two LLM calls for one row and an annotation whose halves came from different annotators — unattributable in the `annotator` column, which is the lineage guarantee §6 rests on.
- **Escalated rows carry `confidence = NULL`.** The LLM emits no calibrated probability. Writing the LR's confidence would misattribute it and writing 1.0 would fabricate certainty; null is the honest value and keeps `AVG(confidence) WHERE annotator='logreg'` meaningful.
- **Boundary is inclusive** (`>= threshold` keeps the row), asserted in tests so a later refactor can't silently flip it.

## Entry #10 — Hybrid merge/rerank design (W2.1 walkthrough)

**Decision — weighted score fusion, the V0 in Section 4, with three rules:**

1. **Metadata filters are a hard pre-filter, applied before scoring.** Both BM25 and vector scores are corpus-relative; scoring the whole corpus and filtering afterwards yields scores that don't correspond to the returned set, and BM25's IDF term would still reflect documents that were filtered out. Pre-filtering also makes "show me only Tier-3 skincare on Meta" mean exactly what a user expects.

2. **Normalize per-query, then weight 0.5/0.5 semantic/BM25.** BM25 scores are unbounded and query-length dependent; cosine similarity is roughly [0,1]. Summing them raw would let BM25 dominate arbitrarily. Min-max normalization *within each query's result set* puts both on [0,1] before weighting. An equal split is the honest starting point — there is no eval data to tune it against (B2), and a tuned weight without a golden set would be a fabricated result. `SEMANTIC_WEIGHT` is one named constant so W2.8 can sweep it the moment a golden set exists.

3. **Dedupe by `creative_id`, keeping the max component score and recording every representation that matched.** A creative can match on its card, its analyst summary, and BM25 simultaneously — that is three hits on one record, not three results. Taking the max rather than the sum avoids rewarding a creative merely for being indexed twice, which would otherwise mean the two-representation design (§8) silently inflates its own ranking. The list of matching representations is retained on the result (`retrieved_by`) because W2.7 needs to know *which* representation matched.

**Rejected: reciprocal rank fusion.** RRF is the more standard choice and is rank-based, so it sidesteps normalization entirely. It was rejected because it discards score *magnitude* — the difference between a 0.9 and a 0.4 match becomes just "first and second." At a 9-row corpus (B2) every query returns nearly everything, so magnitude is the only signal separating a real match from a weak one, and an explainable weighted sum is easier to defend in an interview than a tuned RRF constant. Revisit if the corpus grows past a few thousand records.

**Rejected for V0: an LLM or cross-encoder reranker.** It is explicitly the Section 4 stretch. It also cannot be evaluated without a golden set, so adding it now would be sophistication with no measurement — precisely the tradeoff the project's philosophy resolves the other way.

## Entry #11 — Recall@5 counting rule (W2.7 walkthrough)

**The question:** a creative is indexed under two representations (card and analyst summary). If the card matches for query Q and the summary doesn't — or both match — what does Recall@5 count?

**Decision: deduplicate to creative IDs first, then compute set metrics over IDs. A creative counts once, no matter how many of its representations matched.**

- `Recall@5 = |relevant ∩ retrieved_top5_ids| / |relevant|`
- `Precision@5 = |relevant ∩ retrieved_top5_ids| / |retrieved_top5_ids|` (denominator is the actual number returned, which can be under 5 on a 9-row corpus — using a literal 5 would silently penalize small result sets for the corpus's size rather than the retriever's quality)

**Why:** the golden set labels *creatives* as relevant, not representations — a human labeling "which ads are relevant to this query" has no view of the index's internals. Counting representations would make the metric depend on an implementation detail (how many ways we happen to index a record) rather than on retrieval quality, and would let the two-representation design inflate its own score against the single-representation baseline it is being compared to. The semantic-vs-hybrid comparison is only fair if both sides are scored in the same units: creative IDs.

**Consequence for the eval harness:** dedupe happens in the retriever, not the metric, so the metric receives a clean ID list. `citation_correctness` (W4.8) uses the same unit, which keeps retrieval and generation metrics directly comparable.

## Entry #12 — Streamlit server segfault on first search (W2.9, debugging)

**Symptom.** The app started fine and rendered every page, but the *first search* killed the server process outright — no traceback, no Python exception, connection dropped and the browser fell back to "CONNECTING". Nothing in the Streamlit log.

**Wrong first hypothesis.** The obvious suspect was PyTorch: the search is the first thing that loads `sentence-transformers`, and torch-in-a-thread crashes are common. Disabling Streamlit's file watcher (`--server.fileWatcherType none`), the standard fix for the known torch/watcher interaction, **did not help** — the server died the same way.

**Actual root cause, from the macOS crash report** (`~/Library/Logs/DiagnosticReports/`), not from guessing:

```
EXC_BAD_ACCESS (SIGSEGV) at 0x18
libarrow.2500.dylib  mi_heap_main
libarrow.2500.dylib  mi_thread_init
libarrow.2500.dylib  _mi_malloc_generic
...
_dataset.cpython-312-darwin.so  __pyx_pymod_exec__dataset
```

Not torch at all — **PyArrow**. Arrow's bundled **mimalloc** allocator segfaults during thread-heap initialization when a pyarrow submodule (`pyarrow._dataset`) is first imported inside Streamlit's script-runner thread. Streamlit reaches pyarrow through `st.dataframe`, which the corpus-health panel calls.

**Fix.** `ARROW_DEFAULT_MEMORY_POOL=system` — switch Arrow off mimalloc to the system allocator. Set via `os.environ.setdefault` at the top of `app/shared.py`, which every page imports before touching Chroma or dataframes. Verified: with the env var set *only* in code and nothing at the launch command, search completes and the server survives.

**Why the env var and not a code restructure:** the crash is inside a C++ allocator during module init — there is no Python-level ordering fix that reliably prevents it, and the system allocator costs nothing at this corpus size. It is one line with a comment pointing here.

**Lessons.**
1. **The crash report was the whole investigation.** A segfault produces no Python traceback, so the temptation is to guess from the symptom — and the plausible guess (torch) was wrong and cost a fix attempt. macOS writes a full native backtrace for every SIGSEGV; reading it named the library, the allocator, and the exact module in one step.
2. **`AppTest` reproduced it faster than the browser.** Streamlit's own test harness segfaulted identically (exit 139) with no UI in the loop, which confirmed it was a real server crash and not a browser/automation artifact.
3. **This would have shipped.** It reproduces on the deploy path (W6.1) and kills the app on a recruiter's first click. Worth carrying into W6.2 as an already-applied fix rather than rediscovering it under deploy pressure.

**Bonus observation, recorded for the case study.** The query "authority-led moisturizer" retrieves the moisturizer ad with semantic score 1.000 and BM25 score 0.000 — the ad copy contains none of those words. That is the §8 two-representation design doing exactly what it was chosen to do, and it is the concrete example to use when explaining why hybrid beats keyword-only. It is an illustration, not a measurement (B2).

## Entry #13 — Search is a form, not a live text input (W2.9)

**Decision:** the explore page wraps its search box in `st.form` with an explicit **Search** button.

**Why:** a bare `st.text_input` re-runs the script on every keystroke, and each run triggers an embedding pass over the query — visibly laggy and wasteful. The form defers the run until submit. It is also more discoverable than Streamlit's small "Press Enter to apply" hint, and it gives the demo a clickable target rather than a keypress.

## Entry #14 — Analyst agent loop bounds (W3.1 walkthrough)

**Shipping the V0 from Section 4: a fixed pipeline, not a dynamic agent.** The tools are called in a set order with a coverage check and a structured trace at every step. Dynamic tool ordering is the stretch and is not scheduled.

**Why fixed order is the right V0 here, not just the cheap one:** the product's claim is explainability. A fixed pipeline produces the same trace shape every run, which means the "How this was produced" expander is legible and the eval harness compares like with like across runs. A dynamic agent that picks its own tool order would make each run's trace a different shape and turn every eval regression into "did the pipeline change or did the model choose differently?" — a debugging cost with no user-visible benefit at this corpus size.

**The bounds:**

- **`MAX_TOOL_CALLS = 8`.** The fixed pipeline uses five. The headroom absorbs one retry and one clarification round without allowing a runaway loop. Exceeding it raises rather than truncating silently — a partial report that looks complete is worse than an error.
- **`MIN_COVERAGE = 3` retrieved creatives.** Below three, no honest prevalence statement is possible: "appears in 2 of 2 examples" reads as a pattern but is noise. Under the floor the agent returns a report that *states the coverage gap as its finding* rather than inventing patterns — the honest failure mode, and the one the honesty rule demands.
- **Clarifying question:** asked when the brief names no product category and no audience. Exactly one round, then it proceeds with what it has. Repeated clarification is a worse experience than a caveated answer, and an agent that can loop on questions can hang the demo.
- **Self-check before returning:** every cited ID must appear in the retrieved set. Uncited or wrongly-cited claims are dropped, not flagged — the honesty rule is a gate, not a warning label. This is the same rule `citation_correctness` (W4.8) measures, applied at generation time rather than only in eval.

**Trace object:** every step records tool name, inputs, output summary, and duration. It feeds both the UI expander and Phoenix (W3.4), from one structure — two renderings of one trace, never two separately-maintained logs that can disagree.

## Entry #15 — Reviewer flag rules (W3.7 draft, W4.4 finalized)

Four checks. Two are deterministic (no LLM, no key, always runnable); two use the LLM. The V0 in Section 4 is the two that create demo moments — unsupported claims and similarity — and both are implemented deterministically first so the reviewer works with no API key at all.

**1. Unsupported efficacy / health claim — severity `claim` (red).**
Triggers on regulated skincare claim language: `clinically proven`, `dermatologist tested/recommended`, `FDA approved`, `cures`, `heals`, `eliminates`, `permanent`, `medical grade`, `reverses`, `repairs damage`, plus quantified outcome claims (`reduces wrinkles by 47%`, `results in 7 days`).

A claim is **flagged unless it is supported by a cited retrieved creative that makes the same claim**. That is the load-bearing rule: the reviewer isn't asking "is this true?" — it has no way to know — it is asking "does the evidence this concept cites actually contain this claim?" An unsupported claim is a claim the generator invented, which is precisely the honesty-rule violation. Evidence on expand shows the matched span and which cited creative was checked.

**2. Similarity to a retrieved ad — severity `similarity` (amber).**
Token-level Jaccard over the concept's headline+body vs. each retrieved creative's copy. **Threshold 0.6** (W4.4). Above it, the concept is close enough to a real ad to raise a plagiarism/derivative concern worth a human's attention. Chosen deliberately conservative — this flag is advisory (amber, non-blocking), so a false positive costs a glance while a false negative could ship a near-copy of a real advertiser's ad. Jaccard rather than embedding similarity because it is explainable in one sentence and the overlapping tokens can be *shown* as the evidence.

**3. False scarcity — severity `claim` (red).**
`limited stock`, `only N left`, `today only`, `last chance`, `ends tonight`, countdown language — flagged when the brief supplies no actual promotion window. Note for the demo: **every one of the nine corpus ads contains "Limited stock"** (B2), so on the current corpus this check flags essentially everything. That is a corpus artifact, not a reviewer bug, and the flag text says so.

**4. Prohibited targeting language — severity `claim` (red).**
Copy addressing protected attributes or implying a health condition: age-shaming, skin-tone targeting, `for problem skin`, appearance-based inadequacy framing. Deliberately narrow, since over-flagging ordinary skincare vocabulary would make the reviewer noise.

**Design rule across all four:** every flag carries `evidence` as a required schema field — the matched span and why it matched. A flag a reviewer can't justify on expand is an unexplainable judgment, which is what this project exists to avoid. `severity` drives colour only; `passed` is false if any `claim`-severity flag exists, so amber similarity never blocks.

## Entry #16 — BM25 negative scores silently dropped valid matches (W3.3, debugging)

**Symptom.** An analyst-agent test failed the coverage gate: a query that obviously matched every document in its fixture retrieved **zero** results.

**Root cause.** `rank_bm25`'s `BM25Okapi` computes IDF as `log((N - n + 0.5) / (n + 0.5))`, which goes **negative** once a term appears in more than roughly half the documents. `CuratedCorpusConnector.search` filtered results with `if score > 0`, on the reasoning that "a zero score means no term overlap." That reasoning is wrong: a *negative* score means the term is common, not that it is absent. Every match on a common word was being discarded.

**Why it mattered on this project specifically.** With a 9-row corpus (B2), "common" arrives almost immediately — measured on the real corpus, `"experience"` and `"limited stock"` appear in **9 of 9** documents and `"skin"` in 7 of 9. The bug's blast radius grows as the corpus shrinks, which is exactly the wrong direction, and it would have looked like "hybrid retrieval is weak" rather than "keyword retrieval is broken."

**Fix.** Decide relevance by **actual term overlap** between the query and the document, and use the BM25 score only for *ranking* among those candidates — including when it is negative. Ordering is unaffected (BM25 remains monotone in relevance); only the inclusion test changed. Ties break on `creative_id` so eval reruns are deterministic.

**Test.** `test_matches_survive_negative_bm25_scores` builds five identical documents, asserts all five are returned, and asserts as a precondition that their scores really are negative — so the regression cannot be "fixed" by a change that merely makes the scores positive.

**Lesson.** The failing test was in the *agent* layer, three modules above the bug. The coverage gate (Entry #14) is what surfaced it: a retriever returning nothing looked, from inside the agent, exactly like a legitimately thin corpus. A guard designed for honesty caught a correctness bug — worth noting, since the temptation with a small corpus is to assume every empty result is a data problem.

## Entry #17 — Insight-tree feature set and depth cap (W3.5 walkthrough)

**Label:** `proxy_bucket` (high/mid/low), per F1. Confirmed.

**Features — deliberately only what a strategist could act on:**
- `hook_type` (one-hot, from `annotations`)
- `tone` (one-hot, from `annotations`)
- `platform` (one-hot)
- `headline_length` and `body_length` (word counts)
- `has_offer_language`, `has_ingredient_mention`, `has_authority_language` (binary, from the same vocabularies the reviewer uses)

**Excluded, and why:** `advertiser` — it would let the tree memorize "CeraVe ads run long," which is true, useless, and reads as a claim about a brand rather than about creative. `days_active` and `variant_count` — these *are* the label (`proxy_bucket` is computed from them, Entry #5), so including them would let the tree reconstruct the label exactly and report ~100% accuracy that means nothing. `date_observed`/`start_date` — calendar artifacts of when curation happened, not properties of the ad.

**Depth cap: 3.** Non-negotiable for interpretability — the deliverable is *rules a human reads as sentences*, and a depth-4+ tree produces conditions no one can hold in their head. With Tier-3 at 100–200 rows, depth 3 is also near the statistical limit: at depth 4 the average leaf holds fewer than 10 rows and the rules are noise. `min_samples_leaf = 5` for the same reason — a leaf built on two ads is not a pattern.

**Wording rule for extracted rules (the judgment part).** Every rule renders as a prevalence sentence with the proxy named as a proxy, never as an outcome:

> "Among the 34 retrieved ads that are ingredient-led and clinical in tone, 22 fall in the high longevity-proxy bucket — meaning the advertiser kept running them longer. This is a spend-persistence pattern in this corpus, not evidence that this combination performs better."

Banned in rule text: *performs, works, converts, wins, drives, best, effective, successful*. A test asserts none of these appear in generated rule sentences, so the honesty framing is enforced mechanically rather than by reviewer discipline.

**Status: cannot be trained.** Tier-3 does not exist (B1), so there is no label column. The module is built and unit-tested against a synthetic frame; it has never seen real data. `train_tree` refuses rather than fitting on too few rows, for the same reason the annotator does.

## Entry #18 — MCP tool contracts (W5.1 walkthrough)

**Four read-only tools.** Note the §9 MCP tool list differs from the five *agent* tools — `get_category_stats` and `generate_evidence_report` are MCP-specific, because an external coding agent wants corpus-level orientation and a citable summary, not the app's internal concept pipeline.

| Tool | Input | Output |
|---|---|---|
| `search_creatives` | `query: str`, `limit: int = 5`, optional `source_type` / `platform` | Ranked hits: creative_id, headline, body, advertiser, platform, source_url, score, matched_via — plus a coverage statement |
| `get_creative_details` | `creative_id: str` | Full source record, its annotations (with `annotator`), analyst summary if present |
| `get_category_stats` | optional `category` | Counts by tier / platform / hook_type / tone, rights-note coverage %, and the corpus caveat |
| `generate_evidence_report` | `query: str`, `limit: int = 8` | Retrieved IDs, prevalence patterns, coverage statement, honesty rule — no LLM call |

**Read-only guarantee, enforced three ways** (AGENTS.md: "No writes from the MCP server"):
1. The server imports only query functions; no `save_*`, `insert_*`, or `write_*` symbol is imported.
2. Its SQLite connections open with the `file:...?mode=ro` URI, so a write attempt fails at the driver rather than relying on discipline.
3. A test asserts a write through the server's own connection raises `OperationalError`.

**`generate_evidence_report` makes no LLM call.** It assembles retrieval output and prevalence counts deterministically. Two reasons: the MCP server must work with no API key (matching the retrieval-needs-no-key rule), and a tool that silently spends the user's tokens when called from someone else's coding agent is a bad citizen. The "report" is evidence assembly, not generation — and it is named to say so.

**Every tool output carries the coverage statement and the honesty rule.** The MCP surface is the one place output travels *outside* our UI, where the footer we control is absent. The framing has to ride along in the payload or it is lost exactly where it matters most.

## Entry #19 — Pydantic version squeeze between mcp and phoenix (W5.2, debugging)

**Symptom.** Importing the MCP server raised, at *class-definition* time:

```
RuntimeError: Unable to apply constraint 'host_required' to schema of type 'function-wrap'
```

**Cause.** A three-way version squeeze on a single shared dependency:
- `mcp` 1.6.0 uses an `AnyUrl` constraint that **pydantic 2.10.0** cannot apply (fixed later in the 2.10 line).
- Upgrading to **pydantic 2.11.9** fixed `mcp` but broke `strawberry-graphql` (a Phoenix dependency), which imports `pydantic._internal._typing_extra.is_new_type` — removed in 2.11.

So 2.10.0 breaks the MCP server and 2.11.x breaks tracing. Rather than ping-pong, I tested candidate versions against **both** imports at once and pinned the one that satisfies both: **`pydantic==2.10.6`**.

**Lesson, and it is the same one as Entry #6.** This is the second time an *unpinned or wrongly-pinned shared dependency* has broken a subsystem far from where the version was chosen. Both times the failure surfaced as "the new module is broken" rather than "the pin is wrong." Two libraries pinned exactly (`mcp`, `arize-phoenix`) still left a shared transitive dependency free to be wrong for one of them. **A lockfile at W6.1 is now a real deliverable, not a nicety** — a grader running `pip install -e .` today can still resolve a different pydantic than this one.

## Entry #20 — Vector search has no relevance floor (W5.2, known limitation)

**Observed.** An off-topic query still returns the corpus's nearest neighbours. Measured raw cosine on the top-3, same index:

| Query | Top-3 raw cosine |
|---|---|
| "gentle cleanser for sensitive skin" | 0.673, 0.665, 0.662 |
| "cryptocurrency derivatives trading" | 0.595, 0.593, 0.563 |
| "how to fix a bicycle" | 0.434, 0.433, 0.431 |

Raw similarity *does* separate relevance. But two things make it look more confident than it is: vector search returns k neighbours regardless of relevance, and per-query min-max normalization (Entry #10) maps the best result to **1.0 every time** — including when the best result is junk.

**Decision: do not add a similarity floor yet.** The gap between genuinely relevant (0.67) and off-topic-but-plausible (0.59) is ~0.08. Picking a cutoff in that band without a golden set (B2) would be tuning on three hand-picked queries, and a floor set slightly too high silently returns nothing for real queries — a worse failure than returning weak results with an honest coverage statement. This is the same reasoning as Entry #9's threshold: pick it when there is data to pick it from.

**Mitigation in the meantime.** The coverage statement travels with every result set (including through MCP), and the UI states that the score is retrieval similarity rather than evidence of performance. **When the golden set exists, sweep the floor alongside `SEMANTIC_WEIGHT` in W2.8 and record the chosen value here.**
