# CreativeSignal — Case Study (Draft)

> **Status: first draft for human edit.** Structure and claims below are
> grounded in `AGENTS.md`, `implementation.md`, `docs/prd.md`, and
> `docs/decision-log.md`. Eval numbers are placeholders until Week 5 data
> exists — nothing here should read as a measured result yet.

## The problem

A freelance or solo skincare marketer runs several client accounts at once
with no in-house creative team and — critically — no internal
legal/compliance function. They move fast across brands and are personally on
the hook when a client's ad is rejected or flagged for an unsupported efficacy
claim ("clinically proven," "reduces wrinkles").

For this persona, a policy review isn't a nice-to-have double-check. It *is*
the compliance function — there is no one else. CreativeSignal exists to give
that marketer evidence-backed patterns from real skincare ads and reviewable
concept drafts with policy risk flagged automatically, so they can move fast
and catch problems themselves.

## The honesty-rule design philosophy

Every design and wording decision in this project is downstream of a single
non-negotiable sentence, reproduced verbatim in every output:

> "Every insight is traceable to examples; every recommendation is a
> hypothesis, not a performance claim."

The practical consequences:

- **Prevalence, not performance.** The product says "pattern prevalence,"
  "engagement proxy," "longevity proxy" — never "what performs best" or
  "winning ads." There is no causal performance claim anywhere.
- **Traceability is mandatory.** Every generated report and concept cites
  creative IDs plus source links and ends with a coverage statement
  (e.g. "Based on 18 retrieved examples; descriptive, not causal.").
- **Descriptive-by-construction labels.** The insight model's label is a
  *longevity proxy* (`days_active`, `variant_count` buckets) rather than an
  engagement metric the corpus doesn't actually carry (see F1 in
  `implementation.md`). "Long-running / heavily-varied ads are ones the
  advertiser keeps paying for" is a defensible, clearly-descriptive heuristic.

This framing was chosen over sophistication on purpose. Explainability and
measurability beat every other tradeoff in the build.

## Key architectural decisions

Summarized from `docs/decision-log.md` and `implementation.md` — real
decisions made on this project, not new content.

### 1. Vertical: skincare (Decision Log #1)

Chosen because it has the densest coverage in the Meta Ad Library among the
three candidates, both Tier-2 ad-copy datasets contain beauty/skincare rows,
and — most importantly — skincare's regulated efficacy claims make the
Reviewer agent genuinely load-bearing rather than decorative.

### 2. Source/annotation table split (Decision Log #3)

The corpus keeps `creatives` (observed facts + deterministic derivations) and
`annotations` (model judgment calls) as **separate tables, never merged**. The
dividing line is "did a model exercise judgment," not "was this computed."
So the F1 longevity-proxy fields (`days_active`, `proxy_bucket`,
`variant_count`) live in `creatives` — they're deterministic arithmetic, not
model judgment — while `hook_type`/`tone`/`confidence`/`annotator` live in
`annotations`. A third `runs` table (added W4.6b) persists generation outputs.

### 3. Retrieval unit: structured record, not chunks

No document chunking. The retrieval unit is a structured creative record with
two representations — the creative card and the analyst summary. This is the
product's core design claim and it's what makes citation-traceability possible.

### 4. Local-first, no-key retrieval

ChromaDB (local persistent), `BAAI/bge-small-en-v1.5` as the single embedding
model everywhere, and `rank_bm25` for keyword retrieval. The retrieval path
runs with no API key at all; `ANTHROPIC_API_KEY` is the only secret in the
system. No cloud databases, no scrapers, no live Meta/TikTok calls — the
corpus is curated local data.

### 5. Two-tier LLM split

Haiku-class for high-volume calls (annotation escalation, analyst summaries)
and Sonnet-class for synthesis and review (agent synthesis, concept
generation, reviewer). This mirrors the product's own cost story. All calls go
through a single wrapper (`src/creativesignal/llm.py`) with retries, cost
logging, and Phoenix tracing — never direct `anthropic` client usage.

### 6. Plain Python + Pydantic, no agent framework

Agents are plain Python loops with Pydantic-typed tool functions — no
LangChain/LlamaIndex/CrewAI. Maximum explainability: there is no abstraction
layer you'd have to explain around in an interview.

### 7. Stretch scope is explicitly gated (Decision Log #2)

A `visual_direction` text field on Concept was defined but *not scheduled* —
actual image generation would require a second vendor API key and violate the
"no extra keys" rule. It sits in the cut order (fine-tune → A2A → image
drafts → MCP) as a kill-switched stretch item, not a default.

### 8. MCP server as the differentiator (Week 5)

Four read-only tools over the same corpus (`search_creatives`,
`get_creative_details`, `get_category_stats`, `generate_evidence_report`)
expose the tool layer to external clients. The read-only guarantee is
non-negotiable: the server queries the corpus, it never writes to it.

## Tool-routing approach

The working model is a judgment-vs-mechanical split across three tools plus
the human, fixed in `implementation.md` and binding throughout:

| Tool | Owns | Examples |
|---|---|---|
| **CC** (Claude Code) | Component/architecture design, prompt design, tradeoff judgment, **all debugging** | schema design (W1.3), hybrid retrieval (W2.5), reviewer agent (W4.5) |
| **KC** (Kilo Code, `deepseek-v4-flash`) | Boilerplate, scaffolding, data loaders, sklearn scripts, MCP server impl, standard UI | loaders (W1.4), Chroma index (W2.4), explore page (W2.9), MCP server (W5.2) |
| **Chat** (claude.ai) | PM judgment, honesty-language wording, week-end checkpoints, visual prototyping via Artifacts | taxonomy freeze (W1.5), walkthroughs, reviewer rubric draft (W3.7) |
| **Human** | Curation, labeling spot-checks, human eval, decisions of record | Tier-3 curation (W0.3), hand-verify 50 rows (W1.7) |

Two supporting rituals make the split observable rather than asserted:

- **Walkthrough-before-build.** Non-trivial tasks get a Chat walkthrough that
  produces a decision-log entry *before* the build prompt, so the coding agent
  implements a decided approach rather than inventing one.
- **Spot-check (⚖️).** One task per week is re-run in Claude Code and diffed
  against the KC output for ~10 minutes, with a paragraph logged in the
  decision log. This is the raw material for the model-selection / cost-tier
  findings section below.

A hard lesson from the log (Decision Log #4): a coding agent's self-reported
"done" is not evidence. Only `git log` (a new commit exists) and direct
inspection of file contents count. This is now standing practice after a
Cloud-Agent false-completion pattern.

## Results

**[eval results table - Week 5 data]** — Recall@5 / Precision@5 (target
~0.70), citation-correctness, Ragas groundedness/faithfulness, and the
6-dimension human rubric, each with sample sizes, go here once `make eval`
and the Week 5 human rubric run are complete.

**[model-routing / cost-tier findings from the ⚖️ spot-check log]** — the
KC-vs-CC comparison paragraphs and the LLM cost story (LR-vs-escalated
annotation rate and token cost from `eval/cost_log.csv`) belong here.

**[cost log numbers]** — annotation escalation rate and per-run token cost.

## What I'd do with production data

*(To be written by the human editor — this section is explicitly a
judgment-artifact deliverable, per Week 6. Placeholder retained so the
draft's scope is visible.)*

[placeholder — production-data expansion notes]
