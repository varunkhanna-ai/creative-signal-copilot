# CreativeSignal — Decision Log

## BLOCKERS — NEEDS HUMAN REVIEW

*Running note. Each entry states what is blocked, what unblocks it, and what was built anyway so the blocker is the only remaining gap.*

### ~~B1 — Tier-3 corpus does not exist~~ — RESOLVED

`data/raw/tier3_meta_sample.csv` landed: **95 real curated rows**, scope logged in Entry #22. Loaded, recalibrated (Entry #23), and the tree now trains on it (Entry #27). Corpus is **104 creatives** (95 Tier-3 + 9 Tier-2), 95 with resolvable source links.

**Not fully clean — kept visible rather than smoothed over:** `variant_count` is a constant 20 across every row (Entry #23, likely a scrape artifact or page-size cap — worth re-curating if real per-ad counts can be recovered); 4 rows carried an unrendered `{{product.brand}}` template placeholder in `body_copy` (Entry #24, handled at load); `category` needed normalization for case and one typo (Entry #24); only 39 distinct ad-copy texts across 93 non-empty Tier-3 rows — genuinely different ads (distinct URLs, dates, durations) sharing repeated creative copy, left as-is since deduping would destroy real observations (Entry #24).

### ~~B2 — Tier-2 corpus too small~~ — SUPERSEDED

Tier-2 is still 9 rows (unchanged, still real), but the corpus this blocked eval on is now 104 rows with Tier-3 present. **Still open: no golden set exists (W2.6, Human).** Retrieval metrics (Recall@5/Precision@5, semantic-vs-hybrid) remain unmeasured — not because the corpus is too small anymore, but because there are no hand-labeled relevance judgments to score against. `make eval` correctly reports "Golden set is empty — nothing to evaluate" rather than fabricating a number. This is the one number in the original plan still genuinely blocked on human work, tracked as new blocker **B5** below.

### ~~B3 — API key unreachable~~ — RESOLVED

`.env` now present in this worktree. Real LLM calls executed: 98 bootstrap labels, 5 escalations, 104 analyst summaries, 6 end-to-end generation runs. Total logged spend **$0.5350** (`eval/cost_log.csv`). One real API compatibility bug found and fixed along the way (Entry #29 — `temperature` deprecated on Sonnet 5).

### B5 — Golden set does not exist (blocks all retrieval eval numbers)

W2.6 (Human, 20 queries × 3–5 hand-labeled relevant creative IDs) has not been done. This is now the **only** remaining blocker on retrieval metrics — the corpus (104 rows, real provenance) is no longer the limiting factor. `make eval` is wired, runs against the real 104-row corpus and real indexes, and will produce Recall@5/Precision@5 for keyword-only/semantic-only/hybrid the moment a golden set exists.

**What is measured instead, honestly scoped:** citation correctness across 6 real end-to-end generation runs (15 concepts) — **1.000**, n=15 concepts. This is a generation-quality metric, not a retrieval metric, and the sample is 6 hand-written briefs, not a golden-set evaluation. See Entry #29.

**Unblocked by:** W2.6, 20 realistic queries with hand-labeled relevant IDs against the real 104-row corpus. `eval/golden_set.jsonl` still carries only the format spec.

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


## Entry #5 — Local environment setup + Phoenix pytest plugin bug

**Setup (one-time, done W1.3):** Python 3.12 not present by default on macOS — installed via `brew install python@3.12` (landed at `/opt/homebrew/bin/python3.12`). Created venv with `python3.12 -m venv .venv`, activated with `source .venv/bin/activate`, then `pip install -e .` to pull all 14 pinned dependencies.

**Known issue:** `arize-phoenix==8.0.0` auto-registers itself as a pytest plugin (`pytest11` entry point) and its own internal import (`phoenix/experiments/functions.py` → `phoenix.evals.models.rate_limiters`) is broken in this version, which crashes pytest at startup before it even collects tests — unrelated to any of our own code.

**Workaround:** run tests with plugin autoloading disabled:
```
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/ -v
```
This loses Phoenix's tracing integration for that run, which is fine for schema/unit-level tests. Revisit when Phoenix tracing is actually needed (W2+), since we may need a real fix (version bump or config change) rather than this workaround by then.

**Status:** Standing workaround. Remember to activate `.venv` (`source .venv/bin/activate`) before running any Python command in this repo going forward — a fresh terminal tab defaults back to system Python 3.9, which will fail with `ModuleNotFoundError: No module named 'creativesignal'`.
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

## Entry #21 — Human-scored artifacts are not model-generated (W5.8)

**Decision:** `eval/rubric.md` ships as a scoring **template** — six dimensions, written 1/3/5 anchors, and a bare CSV header row. No example scored row, and no scores anywhere in the repository.

**Why no example row, even a fake one:** a plausible-looking sample row is one copy-paste away from being mistaken for a real record, and it would sit in the same file as the real results once scoring happens. The column list already conveys the format; an example row adds nothing and adds a way to be wrong.

**The larger rule this sets:** a model scoring its own system's outputs measures nothing. The human rubric exists precisely to get judgment from outside the system, so any score I generated would defeat the artifact's purpose while looking like progress. Same reasoning as B1 (not fabricating Tier-3) and the training refusals — the failure mode throughout this project is *plausible output standing in for absent measurement*.

**Status:** rubric finalized; scoring pass outstanding (needs generated runs → needs B3).

## Entry #22 — Tier-3 category scope: skincare + lip balm + deodorant, shampoo excluded (W0.3)

**Decision (human, recorded here):** the curated Tier-3 sample keeps **skincare, lip balm, and deodorant** in scope and **excludes shampoo/haircare**.

**Rationale.** The vertical is "skincare" (Entry #1), and the boundary question is which adjacent personal-care categories share the ad conventions the product reasons about. Lip balm and deodorant do: they are topical, applied to the body, and their advertising uses the same claim vocabulary the Reviewer checks — ingredient-led reasons to believe, dermatologist/clinical authority framing, and sensitivity/irritation claims. Shampoo does not: haircare advertising centres on hair texture, volume, and styling outcomes, with a largely separate claim vocabulary and no skin-contact safety framing. Including it would widen the corpus without widening what the retrieval or reviewer layers can say anything useful about.

**This is also the boundary the W1.4 Tier-2 filter already enforces.** `NON_SKINCARE_PRODUCTS` vetoes `hair`, `shampoo`, and `conditioner` (Entry #7, where "Hair Serum" matched on "serum"). The Tier-3 curation rule and the Tier-2 filter now agree, which matters because the two tiers are searched as one corpus.

**Verified against the delivered file:** 0 rows mention shampoo or conditioner; a single row mentions "hair" incidentally (`T3-006`, a CeraVe body-wash ad whose copy reads "work for BOTH of us"). The exclusion was applied at curation time, so no code-side filter is needed for Tier-3 — the rule is recorded here rather than implemented, and `load_tier3` deliberately does not re-filter what a human already scoped.

**Consequence for the `category` column:** it now holds `lip balm` and `deodorant` alongside the skincare categories. Nothing downstream keys on a closed category set — `category` is a display and filter field, not a label — so no schema or model change follows.

## Entry #23 — Proxy-bucket recalibration, and `variant_count` is unusable (W1.4 / W3.6)

This is the recalibration Entry #5 required "before training the W3.6 tree." The delivered Tier-3 data forced it immediately.

**Finding 1 — every one of the 95 curated ads bucketed `high`.** The original rule (`high` if `days_active >= 90` **or** `variant_count >= 5`) put 95/95 in one class. The tree's single-class guard refused to train, which is the guard working exactly as designed.

**Finding 2 — `variant_count` is the constant 20 for all 95 rows.** Not a distribution, a constant. Measured:

| Field | min | 25% | 50% | 75% | max |
|---|---|---|---|---|---|
| `days_active` | 1 | 5 | 20 | 26 | 173 |
| `variant_count` | 20 | 20 | 20 | 20 | 20 |

A constant column carries zero information, and via the `>= 5` clause it single-handedly forced the degenerate split — only 5 of 95 rows would have qualified as `high` on `days_active` alone.

**Decision.** Drop `variant_count` from the bucket rule and recalibrate on `days_active` alone: **`low` < 10, `mid` 10–24, `high` >= 25**. Result on the real data: **low 36 / mid 31 / high 28**.

- Thresholds stay **fixed, not percentile-based** — Entry #3 requires `proxy_bucket` to be deterministic from its source fields, so a record's bucket must not change when the corpus around it changes. They are now *informed by* the observed distribution (true tertiles 8.0 and 22.7 days) and rounded, rather than guessed.
- `compute_proxy_bucket` still **accepts** `variant_count` and ignores it, so a corrected re-curation needs no call-site change. A test asserts passing it changes nothing.

**What this costs, stated plainly.** F1 specified the proxy as `days_active` *plus* `variant_count`. Half of that is gone. The proxy is now purely a run-duration signal, which weakens it — a heavily-varied short-run ad and a single-creative short-run ad are no longer distinguishable. The honesty framing is unchanged and, if anything, easier to defend: this is spend-persistence, not performance.

**Open for the human (curation gap, not a code bug).** `variant_count = 20` for every row looks like a placeholder or a scrape artifact (20 is a common page-size cap). If real per-ad variant counts can be recovered, re-curate that column and re-run this calibration — the thresholds above would then need re-checking against a two-signal rule.

## Entry #24 — Tier-3 data-quality handling at load (W1.4)

Three issues in the delivered curation, all handled at load rather than by editing the CSV. The CSV is the human's artifact; silently correcting it would make their curation and the loaded corpus disagree.

1. **`category` is hand-typed and inconsistent** — mixed case (`Lotion`, `spf`, `Toner`, `Lip Balm`) plus a typo (`Deodrant`). Normalized to lowercase with an alias map (`deodrant` → `deodorant`, `spf` → `sunscreen`). 7 blank cells become `uncategorized` rather than being dropped.
2. **4 rows carry an unrendered template variable** — `body_copy` is the literal string `{{product.brand}}` (T3-021, T3-022, T3-036, T3-037): the ad library captured the variable, not its value. That is not ad copy, and indexing it would put a meaningless high-frequency token in the corpus. `clean_body_copy` strips `{{...}}` and nulls a body that was *entirely* placeholder. **The rows are kept** — their provenance and `days_active` are real, and the tree uses them.
3. **Heavy duplicate copy is real and is left alone.** Only 39 distinct `body_copy` texts across 93 non-empty rows. Unlike the Tier-2 case (Entry #7), these are **genuinely different ads**: distinct `ad_library_url`, distinct `start_date`, distinct `days_active`. Deduplicating them would destroy real observations and bias the proxy distribution. Noted here because it inflates apparent prevalence — five ads sharing one line of copy is one *creative idea* appearing five times, and any prevalence count over Tier-3 should be read with that in mind.

Post-load corpus: **104 creatives** (95 Tier-3 + 9 Tier-2), 95 with resolvable source links, 98 with usable ad copy.

## Entry #25 — Classes with one example are dropped, not trained (W1.8)

**Finding.** The real bootstrap produced `authority_expert: 1` — a single authority-led ad in 98. The training guard refused the whole axis.

**Decision.** Drop classes below `MIN_ROWS_PER_CLASS` (2) from training and **report them**, rather than refusing the axis entirely. Five of seven hook types are learnable; discarding all of them because one is not would be the wrong trade.

**Why dropping beats keeping.** A single-example class cannot be stratified across CV folds, so it makes honest evaluation impossible. Worse, a classifier nominally "trained" on it would predict it essentially never while still inflating the apparent class count — the model would look like it covers seven hooks when it covers five.

**Why this is safe.** A dropped class does not vanish from the system: the classifier cannot predict it, so any such ad falls below the confidence threshold and **escalates to the LLM**, which can still label it. The two-stage design absorbs the gap by construction. The drop is printed at training time, not swallowed.

**Watch item.** `authority_expert` being near-absent is itself notable, since authority framing ("dermatologist recommended") is a defining skincare convention and the Reviewer's claim check targets exactly that language. Either the curated sample under-represents it or the bootstrap prompt is under-assigning it. Worth checking during W1.7 human verification.

## Entry #26 — Escalation threshold recalibrated to 0.35 (W1.9, supersedes Entry #9)

Entry #9 set 0.70 as a defensible prior with no data. The real out-of-fold threshold table:

| thresh | hook escal% | hook acc@kept | tone escal% | tone acc@kept |
|---|---|---|---|---|
| 0.00 | 0.0% | 90.5% | 0.0% | 79.6% |
| 0.30 | 9.5% | 94.2% | 16.3% | 87.8% |
| **0.35** | **18.9%** | **98.7%** | **41.8%** | **98.2%** |
| 0.40 | 37.9% | 100.0% | 57.1% | 100.0% |
| 0.70 | 92.6% | 100.0% | 98.0% | 100.0% |

**0.70 was badly wrong.** It escalates 93–98% of rows — the classifier would handle almost nothing and the two-stage design would collapse into "always call the LLM," paying full cost for no benefit. This is exactly why Entry #9 flagged it as a placeholder rather than a result.

**Decision: 0.35.** It is the lowest threshold clearing a 95% accuracy-on-kept bar on *both* axes (98.7% / 98.2%). Below it, accuracy on kept rows falls off quickly (0.30 → 87.8% on tone); above it, escalation climbs steeply for a gain of at most 1.8 points.

**Baseline model quality, measured out-of-fold:** hook_type **90.5%** accuracy (macro F1 0.88), tone **79.6%** (macro F1 0.81), n=95/98. Tone is the weaker axis and drives the per-row escalation rate, since escalation triggers on `min(hook, tone)`.

**Two escalation rates, and the difference matters.** Running the full corpus at 0.35 gave **5.1%** (5 of 98 escalated). That number is **in-sample** — the deployed model was fit on the same seed it is now labeling, so it is over-confident on rows it has already seen. The **out-of-fold** table above is the honest production estimate: roughly **40%**, driven by tone. Report 40% as the expected rate and 5.1% only as what this specific re-labeling run cost. Quoting 5.1% as a production figure would overstate the cost saving by roughly 8x.

**Cost so far:** $0.105 total for 98 bootstrap labels plus 5 escalations (Haiku), logged per call in `eval/cost_log.csv`.

## Entry #27 — Tree trained on real data: `platform_count`, and two wording bugs (W3.6)

**The tree trains.** 95 Tier-3 rows, balance low 36 / mid 31 / high 28, depth 3, **in-sample accuracy 0.62** against a ~0.33 three-class baseline. In-sample on 95 rows is directional only and is labeled as such everywhere it appears.

The strongest rule: *among the 9 ingredient-led ads, 8 fall in the high longevity-proxy bucket.* Descriptive, cited, and exactly the shape the honesty rule requires — but note n=9, so it is a lead to investigate, not a finding.

**Fix 1 — `platform` replaced with `platform_count`.** The real Ad Library `platform` field is a comma-separated *placement list* (`FACEBOOK,INSTAGRAM,MESSENGER,THREADS`), not a single value — six distinct combinations across 95 rows. One-hot encoding it made every *combination* its own sparse class and produced rules like "platform is not FACEBOOK,INSTAGRAM,AUDIENCE_NETWORK,MESSENGER,THREADS," which is unreadable and splits on an artifact of how placements were bundled. Replaced with the count of surfaces — an interpretable breadth-of-buy proxy that the tree now splits on meaningfully ("runs on more than 4 placement surfaces").

**Fix 2 — the direction phrase was wrong for `mid`.** `rule_to_sentence` branched on `high` vs. everything-else, so a `mid` rule read "the advertiser kept running them **for a shorter period**" — false, and the kind of small wording error that quietly makes an output untrue. Now mapped per bucket (high → "longer", mid → "for a moderate period", low → "for a shorter period"), with a regression test per bucket.

**Fix 3 — numeric conditions render as English.** `platform count <= 4.5` became the ungrammatical "platform is count <= 4.5" because the categorical humanizer ran first. Numeric features are now phrased before the categorical rules: "the ad runs on 4 or fewer placement surfaces", "the body is longer than 18 words".

**Why these matter beyond tidiness.** The tree's deliverable is *sentences a human reads and repeats*. A rule that is unreadable will be ignored; a rule that is readable and **wrong** is worse — it gets repeated. The honesty enforcement in this module was aimed at performance vocabulary, and it caught none of these, because all three were accuracy failures rather than claim failures.

## Entry #28 — Platform filter never matched a single platform name (W2.5, debugging)

**Symptom.** Filtering the corpus on `platform="facebook"` returned **0 creatives**, silently, despite 95 of 104 rows being Facebook placements. Typing "facebook" into the explore page's sidebar filter produced an empty result set with a helpful-sounding "no matches" message.

**Cause.** The real Ad Library `platform` field is a comma-separated *placement list* — `FACEBOOK,INSTAGRAM`, `FACEBOOK,INSTAGRAM,AUDIENCE_NETWORK,MESSENGER,THREADS` — not a single value. `all_creatives` filtered with `platform = ?`, so only an exact match on the full list string could ever succeed. `parse_filters` maps "meta" and "facebook" to `facebook`, so the natural-language filter path was broken too.

**Fix.** Match membership on comma boundaries, case-insensitively:
`(',' || UPPER(platform) || ',') LIKE ('%,' || UPPER(?) || ',%')`. Boundaries rather than a bare substring, so `"face"` does not match `FACEBOOK` — asserted in a test.

Verified after the fix: facebook 95, instagram 95, messenger 38, threads 38, tiktok 0, unknown 9.

**Why it went unnoticed.** Every test used single-value platforms (`"facebook"`, `"unknown"`), because they were written before real Tier-3 data existed. The fixtures encoded an assumption about the data's *shape* that the real data violated — the same class of miss as the `variant_count` constant (Entry #23) and the `platform` one-hot in the tree (Entry #27). All three surfaced only on contact with real curation.

**Pattern worth stating once:** three separate bugs this session came from the same root — code written against an imagined schema, tested against fixtures built from the same imagination. Tests passing meant "consistent with my assumptions," not "correct." Only real data could distinguish those, and it disagreed three times.

## Entry #29 — `temperature` deprecated on Sonnet 5; a zero-concept run traced to its actual cause (W3.3/W4.3, debugging)

**Error 1 — real API rejection.** The first real generation call failed outright: `anthropic.BadRequestError: 400 — 'temperature' is deprecated for this model`. `llm.complete()` always sent `temperature=0.0`. Fixed by making `temperature` optional (`None` by default) and only including it in the request when a caller explicitly asks for it — so Sonnet 5 is called with no temperature override rather than a rejected one. Consequence, stated plainly: generation calls are no longer deterministic (no fixed temperature=0), which is the direct cause of the finding below.

**Finding — one real run produced zero concepts.** Six real briefs were run end to end (`retrieval → concepts → review`). Five produced 3 concepts each; `run_757a37c86163` ("a ceramide moisturizer for dry winter skin") produced 0.

**Traced, not assumed:**
- Retrieval returned **8 creatives** for this brief — same as every other run, well above the 3-example coverage floor. Retrieval was not the cause.
- `generate_concepts()` returns `[]` exactly two ways: no evidence resolved (not the case here), or `parse_concepts(response.text)` fails to parse the raw LLM output. The agent's own trace notes log every citation-gate drop, and none appeared for this run — ruling out the self-check gate as the cause.
- That leaves one possibility: **the raw Sonnet response for that specific call did not parse as the expected JSON array.** Re-running the identical brief, identical retrieval (same 8 IDs), identical prompt moments later produced 3 well-formed, correctly-cited concepts.

**What is not known, and why.** The run only persisted the *parsed* result (an empty list) — the raw LLM text was never logged, so there is nothing to inspect after the fact to confirm the specific malformation (prose preamble, truncation, a stray code fence variant the parser doesn't handle, etc.). Stating a specific cause beyond "failed to parse" would be a guess dressed as a finding.

**Fixed the actual gap:** `generate_concepts()` now logs the full raw response via `logging.warning` whenever `parse_concepts` returns zero concepts from a non-empty LLM response. A future occurrence is diagnosable; this one is not, and is reported honestly as such rather than backfilled with a plausible-sounding explanation.

**Measured, not estimated — citation correctness across all six real runs:** 15 concepts generated, mean **citation_correctness = 1.000** (n=15; every cited ID was in that run's retrieved set). This is a small sample from six hand-written briefs, not a golden-set eval, and is reported at that scope. One additional run generated zero concepts for the reason above, contributing 0 concepts (not a 0.0 score) to this figure.

**Cost, logged not estimated.** Total across this session's real API usage — 98 bootstrap labels, 5 escalations, 104 analyst summaries, 6 generation runs (including the zero-concept one, which still consumed a call) — is **$0.5350**, read from `eval/cost_log.csv`, not summed by hand.

## Entry #30 — Ragas judge LLM: two real bugs, one diagnosed-but-unresolved (W5.7)

**Bug A — Ragas defaults to OpenAI.** Calling `ragas.evaluate()` with no `llm=` argument requires `OPENAI_API_KEY`, which this project does not have and by design should never need (AGENTS.md: "no extra vendor API keys"). Fixed by wrapping the project's own Anthropic client via `langchain-anthropic` + `LangchainLLMWrapper` and passing it explicitly as the judge — Ragas stays on the one vendor already in use.

**Bug B — `temperature` deprecated on Sonnet 5, injected two layers deep.** Every judge call failed with the same 400 (`temperature is deprecated for this model`) already hit once in `llm.py` (Entry #29) — but fixing `ChatAnthropic(temperature=None)` at construction was **not sufficient**, and it took two follow-up attempts, each verified against a real API call before moving on, to find why:

1. First attempt: pass `temperature=None` to `ChatAnthropic`. Verified standalone with one real call — worked in isolation, still failed inside the full Ragas run (30/30 calls, same 400).
2. Traced by reading actual ragas source, not guessing: `LangchainLLMWrapper.agenerate_text` only calls `self.get_temperature(n)` when its incoming `temperature` argument is `None` — so overriding `get_temperature()` (second attempt) looked like the fix.
3. That still failed, because **one level higher**, `BaseRagasLLM.generate()` (the method every metric actually calls) already replaces an incoming `temperature=None` with a hardcoded `1e-8` *before* `agenerate_text` ever runs. By the time `agenerate_text` sees it, the value is never `None`, so `get_temperature()` is never consulted at all.
4. **Fix:** override `agenerate_text` itself to force `temperature=None` regardless of the value it receives, preserving the original method's branching exactly (the single-completion path and the `n>1` path `answer_relevancy` needs for its `strictness=3` parameter — both verified against real API calls, including the `n=3` path specifically, before re-running the full 30-job evaluation).

**Bug C — diagnosed, not fixed, per explicit instruction to stop at this layer.** With A and B resolved, Faithfulness's NLI-statement-verdict prompt fails to parse Claude's output on the large majority of calls (`RagasOutputParserException`, `n_l_i_statement_prompt` / `fix_output_format`). Two runs: **3 of 15** samples scored, then **0 of 15**. This looks like a genuine output-format incompatibility between this ragas version's parser (built and tested against OpenAI-shaped outputs) and Claude's — not a temperature issue, not something either bug above touches, and not pursued further.

**What is actually reportable, with honest sample counts:**

| Metric | Scored / total | Value | Note |
|---|---|---|---|
| `answer_relevancy` | 15 / 15 (both runs) | 0.573 – 0.627 across two runs | Reliable; no parser failures observed |
| `faithfulness` | 0–3 / 15 | 0.468 (n=3) or NaN (n=0) | **Not usable in its current form** — most calls never produce a scoreable output |

`ragas_eval.py` now reports `n_scored` per metric alongside every score, computed from `EvaluationResult.to_pandas()` — a metric's aggregate mean silently drops unparseable samples, so reporting the bare number without its support would misstate the sample size (the same failure mode B5 exists to prevent for retrieval metrics).

**Not fabricated:** no retrieval golden-set number was approximated from the corpus to fill this gap, per instruction. `make eval` still reports "Golden set is empty" and nothing else.

**Fair to report today, and reportable without a golden set (also per instruction):**
- **Citation correctness**, post-gate, across all 6 real generation runs: **1.000** (n=15 concepts) — Entry #29.
- **Citation correctness**, pre-gate vs. post-gate, on a separate 3-brief check: **1.000 both**, 0 concepts dropped by the self-check gate — Entry #29.
- **Planted-violation reviewer test**: passes (`test_planted_prohibited_claim_is_flagged`), deterministic, no key required.
- **Ragas `answer_relevancy`**: 0.573–0.627 across two independent runs, n=15.
- **Ragas `faithfulness`**: not usable pending a parser fix or a ragas version upgrade — reported as broken, not papered over with a partial-sample number presented as complete.

## Entry #31 — `.env` silently ignored: `~/.zshrc` exports a blank `ANTHROPIC_API_KEY` (debugging)

**Symptom.** `.env` was confirmed present, correctly formatted, and found successfully by `load_dotenv()` in isolation — yet the Streamlit app reported "No ANTHROPIC_API_KEY configured" every time, after every restart.

**Root cause, found by instrumenting the real call path rather than re-testing the parts already confirmed working.** `~/.zshrc:11` contains `export ANTHROPIC_API_KEY=""`. Any terminal that sources that profile — including the one `streamlit run` is launched from — starts with `ANTHROPIC_API_KEY` already present in its process environment, set to an empty string. `python-dotenv`'s `load_dotenv()` defaults to `override=False`: if the variable already exists in `os.environ` at all, it leaves it alone, even if the existing value is empty and the `.env` file has a correct one sitting right next to it. `has_api_key()`/`_client()` then read `os.getenv("ANTHROPIC_API_KEY")` and get back `""`, which is falsy — indistinguishable, from the app's side, from ".env was never found."

**Why isolated testing missed it.** Calling `has_api_key()` from a plain `python -c "..."` one-liner in an *already-open* Bash tool session — one that had not freshly sourced `~/.zshrc` — never had the blank variable in its environment to begin with, so it worked every time in exactly the way that made the bug look like it couldn't be real. The failure only reproduces in a shell that has actually sourced the profile, which is what a normal terminal launching `streamlit run` does and what my initial ad-hoc checks did not.

**Diagnosis method, in order:**
1. Confirmed `.env` exists, is well-formed, and `load_dotenv()`/`find_dotenv()` resolve it correctly from plain Python — ruled out the file itself.
2. Traced `find_dotenv()`'s actual search algorithm from source rather than assuming cwd-based behavior: it walks upward from the *calling frame's file location* (here, `llm.py`'s own directory), which resolves correctly regardless of Streamlit's working directory or execution model — ruled out a path-resolution bug.
3. Instrumented `has_api_key()` itself to write its actual runtime state (pre-existing env value, `find_dotenv()` result, post-load value) to a file, then drove the **real running app** through the browser rather than a synthetic reproduction — surfaced `env_already_set` before ever changing the check to look at the *pre*-existing value.
4. Corrected the instrumentation to capture the environment variable's value *before* `load_dotenv()` ran (not after), which is what actually named the mechanism: `load_dotenv(override=False)` skipping a variable that already exists.
5. Grepped shell profiles directly rather than guessing further — `~/.zshrc:11` was the source in one line.

**Fix.** `load_dotenv(override=True)` at both call sites (`_client()` and `has_api_key()` in `llm.py`, and the corresponding call in `ragas_eval.py`'s judge-LLM setup). `.env` now always wins over whatever the shell happened to export, which is the correct policy for a project-local secret file regardless of what a user's personal shell profile does.

**Verified, not assumed:** reproduced the exact failure with `ANTHROPIC_API_KEY=""` forced into the environment before the fix (confirmed `has_api_key()` returned `False`), confirmed the fix resolves it in isolation, then re-confirmed under a real `zsh -c "source ~/.zshrc && ..."` invocation — the literal condition the bug report described — both before (fails) and after (passes) the fix.

**Test added:** `tests/test_llm.py`, including one test that pins the actual fix (`load_dotenv` must be called with `override=True`) so a future refactor that quietly drops the kwarg fails loudly rather than silently regressing.

**Not the user's `.zshrc` to fix.** The blank export may be intentional elsewhere (e.g., to make an unset key explicit rather than absent) — the fix belongs in this project's code, which cannot assume every developer's shell environment is clean, not in a personal dotfile outside the repo's control.

## Entry #32 — Eval dashboard never wired to read real generation results (W5.10, debugging)

**What was reported.** The eval dashboard still showed "not yet measured" for citation correctness and Ragas after both had been run for real (Entry #29/#30: citation correctness 1.000 n=15, Ragas answer relevancy 0.57–0.63 n=15).

**Not a staleness bug — a missing-wiring bug.** The page was written at W5.10, before any generation run existed, and was never revisited after those runs landed. Concretely: it never imported `citation_correctness` or `list_runs`, never read `eval/results/ragas_eval.json` (only `retrieval_eval_*.json`, a different file for a different metric), and its "Not yet measured" section was static markdown text listing all four generation metrics as permanently unmeasured — not a check against any data source at all. The annotator section and cost section *were* wired to live queries and were already showing real numbers (98 annotations, $0.535) the whole time; only the generation-metrics section had no wiring.

**Fix.** Added a Generation section computing citation correctness live from the `runs` table (same `citation_correctness()` function the eval harness uses, so the dashboard and the CLI report cannot silently disagree) and loading `ragas_eval.json` directly, including its `n_scored` breakdown so faithfulness's near-total parse-failure rate (Entry #30) is visible as "unusable, 0 of 15 scored" rather than a blank or a misleadingly bare number. Rewrote the "Not yet measured" block to state only what is genuinely unmeasured — the golden set and the human rubric — instead of four items, two of which had real results sitting on disk unread.

**Also fixed in passing:** the retrieval empty-state message still said "the corpus is 9 synthetic ads," a factual claim that stopped being true once Tier-3 landed (B1). Corrected to name the real blocker (the golden set) rather than a corpus-size limitation that no longer exists.

**Verified against the actual artifacts, not assumed:** computed citation correctness and read `ragas_eval.json` directly in a script first, then loaded the real running page and read its rendered text, and confirmed the two matched exactly (1.000/15, 0.573, unusable/0 of 15, $0.5350) before considering this done.
