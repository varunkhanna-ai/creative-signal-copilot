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
