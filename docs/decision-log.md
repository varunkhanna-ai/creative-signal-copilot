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

### B2 — Tier-2 skincare yield is 24 rows, not ~300 (blocks every eval number)

Measured, not assumed. Filtering both ad-copy datasets on ~20 skincare keywords yields **13 rows** from `jaykin01/advertisement-copy` (of 1141) and **11** from `smangrul/ad-copy-generation` (of 1000).

At 24 records, retrieval metrics are not measurements: Recall@5 / Precision@5 over a corpus barely larger than the result set is degenerate, and W2.8's semantic-vs-hybrid comparison — the point of the task — cannot separate the two conditions. **No eval run has been executed and no eval numbers have been committed.** `make eval` is wired and will run; it is deliberately unrun rather than run-and-reported on a corpus that would make the output meaningless.

**Unblocked by:** B1 (Tier-3 lands → ~150–250 provenance-rich rows) plus W2.6 golden set (Human, 20 queries × 3–5 relevant IDs). Both are prerequisites to any number entering `docs/eval-plan.md` or the README results table.

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
