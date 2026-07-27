# AGENTS.md — CreativeSignal project context

Read this fully before any task. This is the single source of truth for all coding agents on this project. Kilo Code reads this file automatically; Claude Code loads it via the `@AGENTS.md` import in CLAUDE.md. The task list lives in `implementation.md`; each session implements exactly one task ID from it.

## What this project is

CreativeSignal: an evidence-backed creative-intelligence copilot for **skincare** ads. A marketer submits a campaign brief; the system retrieves cited examples from a curated public corpus, produces a trend report and 3 reviewable ad concepts, and an independent reviewer agent flags policy issues. Built as a 6-week AI-PM capstone — **explainability and measurability beat sophistication in every tradeoff.**

## The honesty rule (non-negotiable, appears in outputs verbatim)

> "Every insight is traceable to examples; every recommendation is a hypothesis, not a performance claim."

- Always "pattern prevalence" / "engagement proxy" / "longevity proxy" — **never** "what performs best," "winning ads," or any causal performance claim.
- Every generated report/concept must cite creative IDs + source links and end with a coverage statement, e.g. "Based on 18 retrieved examples; descriptive, not causal."
- The insight model's label is a **longevity proxy** (`days_active`, `variant_count` buckets), and all wording around it stays descriptive/correlational.

## Stack (fixed — do not substitute)

Python 3.12 · Pydantic models · ChromaDB (local persistent, `data/chroma/`) · `sentence-transformers` with `BAAI/bge-small-en-v1.5` (the only embedding model, everywhere) · `rank_bm25` · scikit-learn · Anthropic API (`llm.py` defines HAIKU_MODEL for high-volume calls, SONNET_MODEL for synthesis/review) · Streamlit · Phoenix (arize-phoenix) tracing · Ragas + hand-rolled retrieval metrics · Python `mcp` SDK (stdio).

## Never do

- **No LangChain / LlamaIndex / CrewAI** or any agent framework. Agents are plain Python loops with Pydantic-typed tool functions.
- **No document chunking.** The retrieval unit is a structured creative record with two representations: the creative card and the analyst summary (see `retrieval/cards.py`).
- **No scrapers, no live API calls to Meta/TikTok.** Corpus is the curated local data only. `sources/live_stubs.py` stays `NotImplementedError` — it exists to prove the interface, not to work.
- **No cloud databases, no extra vendor API keys.** `ANTHROPIC_API_KEY` is the only secret. Retrieval must run with no key at all.
- **Secrets never touch the repo.** Key comes from `.env` locally and `st.secrets` when deployed; `.env` and `.streamlit/secrets.toml` stay gitignored. The deployed app defaults to **demo mode** (replay from the `runs` table, zero API calls); live generation requires the `st.secrets["demo_password"]` gate (W6.1b). Never write code that makes an LLM call reachable by an unauthenticated visitor on the deployed app.
- **No writes from the MCP server.** All four MCP tools are read-only over the corpus.
- Don't invent schema fields, rename the five agent tools (`search_creatives`, `get_creative_details`, `analyze_pattern`, `generate_concepts`, `run_evaluation`), or add features beyond the current task ID.

## Data layout and lineage

- `data/corpus.sqlite` has **three tables, kept separate on purpose**: `creatives` (source records with provenance: ad-library URL, advertiser, date observed, platform, `source_type`, `rights_note`, proxy fields), `annotations` (derived labels with `annotator` = `"logreg"` or model name, plus `confidence`), and `runs` (persisted generation outputs: run_id, timestamp, brief, retrieved IDs, trend report, concepts, review result, model + prompt versions, token cost — added in W4.6b). Never merge them; never write derived or generated values into `creatives`.
- Annotation flow: logistic regression first (`annotate/classical.py`); rows under the confidence threshold escalate to the LLM (`annotate/escalate.py`). Log token costs to `eval/cost_log.csv` on every LLM call.

## Conventions

- All LLM calls go through `src/creativesignal/llm.py` (single wrapper: retries, cost logging, Phoenix tracing). No direct `anthropic` client usage elsewhere.
- Prompts live in `prompts/` as versioned text files (`name_v1.txt`), loaded by path — never inline multi-paragraph prompts in code.
- Everything runnable is a Make target: `make ingest | annotate | index | eval | slice | app | mcp`. New capabilities get a target.
- Type-hint everything; Pydantic models for every cross-module data shape; small pure functions over classes unless state demands it.
- Tests in `tests/` are smoke-level: schema round-trip, retrieval returns citations, reviewer flags the planted violation. Keep them fast.


## UI design direction (Streamlit) — applies to every page

Goal: clean, credible, consistent. Do not fight Streamlit with custom CSS; use its native theming and a small fixed component vocabulary.

- **Theme** lives in `.streamlit/config.toml` (created in W2.9) and is the only place colors are defined:
  - `primaryColor = "#0F6B5C"` (deep teal — evidence/trust), `backgroundColor = "#FAFAF7"`, `secondaryBackgroundColor = "#EFEFEA"`, `textColor = "#1E1E1E"`, `font = "sans serif"`.
- **Page skeleton, identical everywhere:** `st.title` (short, no emoji) → one-line caption stating what the page does → content → the verbatim honesty footer in `st.caption` at the bottom. Sidebar holds only navigation and global filters.
- **Component vocabulary (use these, nothing exotic):**
  - Creative cards → `st.container(border=True)` with headline bold, body text, then a one-line provenance footer in `st.caption` (advertiser · platform · date observed · source link).
  - Metrics (eval numbers, escalation rate, corpus counts) → `st.metric`, with the §11 target shown as the delta reference.
  - Reviewer flags → colored `st.badge`/pill-style markers inline on the concept: red = claim issue, amber = similarity, gray = informational. Every flag shows its evidence on expand.
  - Agent traces → `st.expander("How this was produced")`, collapsed by default; steps as a numbered list, tool calls in `st.code`.
  - Tables → `st.dataframe` with column config; never raw `st.write` on a DataFrame.
- **Rules:** no emoji in headings or labels; no more than two accent colors in any view; every number visible in the UI must be traceable (link or expander to its source); empty states get one helpful sentence, never a blank pane or a stack trace.
- Layout hierarchy comes from whitespace and `st.columns`, not from horizontal rules or boxes-within-boxes.

## How to work on a task

1. Read the task's row in `implementation.md` (files, functions, output line).
2. If the task had a preceding "Walkthrough" row, the human will paste the decided approach — implement *that*, not an alternative.
3. Build only what the task ID names. Stop when its output line is satisfied. Propose the diff; the human commits.
4. If blocked or debugging isn't converging within ~2 attempts, say so and stop — escalation between tools is the human's call, not yours.
