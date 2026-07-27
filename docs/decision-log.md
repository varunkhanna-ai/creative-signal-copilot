# CreativeSignal — Decision Log

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
