# CreativeSignal — implementation.md

**What this document is.** The executable spec for the 6-week CreativeSignal capstone, derived from the finalized strategy doc. It implements every DECIDED item as written, resolves the [OPEN] items with stated defaults, and flags implementation-level issues only (this file's Section 0.3). Per §16 of the strategy doc, this is a **working-session script, not a delegation ticket**: each week opens with a "why" restatement, each non-trivial task is a walkthrough prompt before it is a build prompt, and each week closes with an "explain it back" checkpoint.

**How tool assignments work.** Every task carries a **Tool** column. Assignments follow the judgment-vs-mechanical split in the strategy doc's Instructions item 5 — they are not interchangeable. Legend:

| Code | Means | When |
|---|---|---|
| **CC** | Claude Code (Claude models) | Component/architecture design, prompt design, anything requiring tradeoff judgment, and **all debugging** — including escalated protocol-level MCP debugging |
| **KC** | Kilo Code, configured with **`deepseek-v4-flash`** as backend | Boilerplate, scaffolding, data loaders, standard UI components, sklearn training scripts, MCP server implementation + client validation |
| **Chat** | Claude (claude.ai chat session) | PM judgment work per §16: interpreting eval results, wording honesty language, cut decisions, week-end checkpoints. Also visual prototyping via **Artifacts** (see flag F3) |
| **Human** | You | Curation, labeling spot-checks, human eval, video, decisions of record |

**Backend note (verified July 2026):** DeepSeek V4 is released; use `deepseek-v4-flash` in Kilo Code's provider settings (OpenAI-compatible API, `base_url` per DeepSeek docs). DeepSeek now uses **peak/off-peak API pricing** (peak = 9:00–12:00 and 14:00–18:00 China time, charged ~2× off-peak) — for a part-time evening/weekend US schedule this mostly works in your favor, but check a rate table once during Week 0 setup. Fallback if Kilo Code's provider list gives trouble: Kimi K2 or Qwen, per the strategy doc's own list.

**Spot-check ritual (learning artifact, per Instructions item 5).** One designated task per week (marked ⚖️ below): after KC produces it, re-run the same prompt in Claude Code, diff the two outputs for 10 minutes, and log one paragraph in `docs/decision-log.md` — what differed, whether it mattered, what you'd route differently next time. This is the model-selection / cost-quality judgment exercise; don't skip it, don't expand it.

---

## Table of contents

- [0. Resolutions, assumptions, and feasibility flags](#0-resolutions-assumptions-and-feasibility-flags)
  - [0.1 \[OPEN\] items — resolved defaults](#01-open-items--resolved-defaults)
  - [0.2 What is implemented exactly as written (no changes)](#02-what-is-implemented-exactly-as-written-no-changes)
  - [0.3 Feasibility flags (implementation-level only, smallest-fix proposed)](#03-feasibility-flags-implementation-level-only-smallest-fix-proposed)
- [1. Repository structure](#1-repository-structure)
- [2. Setup (Week 0, ~1 hr of the half-day)](#2-setup-week-0-1-hr-of-the-half-day)
- [3. Week-by-week plan](#3-week-by-week-plan)
  - [Week 0 — Pre-work](#week-0--pre-work-half-day-as-decided)
  - [Week 1 — Thin vertical slice + classical-ML baseline](#week-1--thin-vertical-slice--classical-ml-baseline-est-18-20h)
  - [Week 2 — Real RAG + eval harness](#week-2--real-rag--eval-harness-est-18h)
  - [Week 3 — Intelligence layer](#week-3--intelligence-layer-analyst-agent--interpretable-insight-est-20h)
  - [Week 4 — Full workflow + reviewer](#week-4--full-workflow--reviewer-est-2224h--flagged-f5-as-the-tightest-week-watch-16-fallback-rule-1)
  - [Week 5 — Differentiator (MCP) + eval depth](#week-5--differentiator-mcp--eval-depth-est-20h)
  - [Week 6 — Recruiter-ready polish](#week-6--recruiter-ready-polish-est-15h)
- [4. V0 / stretch splits for the four riskiest tasks](#4-v0--stretch-splits-for-the-four-riskiest-tasks)
- [5. Learning additions](#5-learning-additions-small-deliberate--do-not-skip-these-to-save-time)
- [6. Handing tasks to Claude Code / Kilo Code](#6-handing-tasks-to-claude-code--kilo-code-how-to-actually-run-this)
- [7. Standing rules during execution](#7-standing-rules-during-execution-binding-from-16)

*(Note: `§` always refers to a section of the finalized strategy doc, referenced externally; "Section N" refers to this file's own numbering.)*

---

## 0. Resolutions, assumptions, and feasibility flags

### 0.1 [OPEN] items — resolved defaults

| Item | Default chosen | Assumption / rationale (one paragraph, not a strategy debate) |
|---|---|---|
| **Vertical** | **Skincare** | Densest coverage in the Meta Ad Library among the three candidates; both Tier-2 ad-copy datasets contain beauty/skincare rows; and skincare's regulated efficacy claims ("clinically proven," "reduces wrinkles") make the Reviewer agent genuinely load-bearing rather than decorative. **If you know fitness apparel or meal-kit better, swap it in Week 0** — the vertical is a filter value and a curation choice, not an architectural one; nothing below changes except dataset filters and example queries. |
| **Embedding model** | **`BAAI/bge-small-en-v1.5`** via `sentence-transformers` | Consistent with the DECIDED local-first stack: no API key in the retrieval path, deterministic and free for the grader to reproduce, runs fine on CPU at this corpus size (~300–600 records). `text-embedding-3-small` would add a second vendor key (LLM is Claude API) for no measurable benefit at this scale. Used consistently everywhere per §7. |
| **Vector DB** (decided pair, pick one) | **ChromaDB** (local persistent client) | Simpler Python API than SQLite+`sqlite-vec` for hybrid workflows; still a local directory the coding agents can read/wipe. See flag F4 for the one known deploy pitfall and its fix. |
| **LLM** | **Claude API**: Haiku-class model for annotation escalation and analyst summaries (high volume, cheap), Sonnet-class for agent synthesis, concept generation, and reviewer | Matches §7 ("Claude API"); the two-tier usage mirrors the product's own cost story. |
| **Observability** | **Phoenix (Arize, open-source)** over Langfuse | `pip install arize-phoenix`, runs fully local — no cloud account or Docker, consistent with local-first and grader reproducibility. |
| **Eval tooling** | **Custom metrics for retrieval** (Recall@5 / Precision@5 are ~30 lines) + **Ragas** for groundedness/faithfulness + the human rubric | DeepEval and Ragas overlap; one framework is enough. Retrieval metrics stay hand-rolled so you can explain every formula in an interview. |
| **Week-5 differentiator** | **MCP server** | The strategy doc's own stated default; also the highest demo value per hour. |
| **Dataset licenses** | Record at Week 0, don't assume | Task W0.4 requires copying each dataset's actual license text/identifier from its Hugging Face card into `docs/data-governance.md` before ingestion. AdImageNet and the two ad-copy sets exist on HF; their license fields are what govern redistribution, so read them from the source of truth rather than from this doc. Tier-3 Meta samples: metadata + copy stored, screenshots only where Ad Library terms permit, `rights_note` populated per record (as DECIDED). |
| **Agent framework** (§7 gives "plain Python + Pydantic (or PydanticAI)") | **Plain Python + Pydantic models** | Maximum explainability per §7's own rationale; PydanticAI adds abstraction you'd have to explain around. |

### 0.2 What is implemented exactly as written (no changes)

Domain and honesty framing (§3 — the "prevalence, not performance" language appears verbatim in the UI footer, README, and every generated report's coverage statement); three-tier data strategy and `CreativeSource` interface (§6); source/annotation table separation (§6); local-first stack (§7); RAG record design — creative card + analyst summary, no chunking (§8); analyst + reviewer agent design and toolset names (§9); MCP tool names (§9); fine-tuning kill-switch (§10 — retained as stretch only, not scheduled); eval targets (§11); vertical-slice sequencing (§12); cut order fine-tune → A2A → image drafts → MCP (§15); all §16 working-style and fallback rules.

### 0.3 Feasibility flags (implementation-level only, smallest-fix proposed)

**F1 — Engagement-proxy label source (§5 Job B) — the one real gap.**
- *Problem:* The DECIDED design trains a decision tree against "an engagement-proxy label (from public engagement signals)." None of the three tiers actually carries engagement data — the Meta Ad Library does **not** expose likes/CTR/spend for ordinary commercial ads (only political/issue ads get spend/impression ranges, and EU reach data is EU-targeted-only), and the Tier-1/Tier-2 research datasets have no engagement columns.
- *Smallest fix:* use an **ad-longevity proxy** instead — `days_active` (Tier-3 ad's Ad Library start date vs. observation date) plus `variant_count` (near-duplicate creatives the same advertiser is running). Both are directly observable at curation time; "long-running / heavily-varied ads are ones the advertiser keeps paying for" is a standard, defensible industry heuristic. Bucket into high/mid/low `proxy_bucket`. New schema fields: `proxy_signal_type`, `proxy_value`, `proxy_bucket`, `proxy_observed_date`. No other change to Job B.
- *Why it's fine:* this *strengthens* the honesty framing — "longevity proxy" is even more obviously descriptive-not-causal than an engagement metric would be.
- *Consequence:* the tree trains only on Tier-3 (100–200 rows) — small but sufficient for an interpretable shallow tree (depth ≤ 3–4); report it as directional, which §11 already requires.

**F2 — Annotator bootstrap circularity (§5 Job A) — needs a defined bootstrap, not a redesign.**
- *Problem:* "Train logistic regression to classify `hook_type`/`tone`, escalate low-confidence cases to an LLM" requires labeled training data before the LR exists.
- *Smallest fix:* a one-time Week-1 bootstrap pass — the LLM labels a seed set of ~250 Tier-2 rows against a fixed taxonomy, you hand-verify a random 50 (≈45 min), correct, then train LR on the corrected seed. From then on the runtime flow is exactly as DECIDED: LR first, LLM only below the confidence threshold. Tasks W1.5–W1.7 encode this.
- *Bonus:* the bootstrap itself becomes a PM talking point (weak supervision + human verification).

**F3 — "Claude Code (with Artifacts)" routing row — feature doesn't live where the table puts it.**
- *Problem:* Artifacts is a claude.ai / Claude Desktop **chat** feature; Claude Code (CLI/IDE agent) doesn't render Artifacts.
- *Smallest fix (preserves the row's intent — visual prototyping on the Claude tier because rendering is a Claude-specific capability, not a model-quality verdict):* **visual prototyping (UI mockups, architecture-diagram drafts) → Claude chat with Artifacts; implementing the resulting Streamlit code → per the normal split** (standard UI components → KC; anything with embedded judgment → CC). Tasks below use `Chat (Artifacts)` for these.

**F4 — Streamlit Community Cloud + Chroma: known sqlite pitfall, known fix.**
- *Problem:* Chroma requires a newer sqlite than Streamlit Cloud's base image ships.
- *Fix (encoded as task W6.2):* add `pysqlite3-binary` to requirements plus the three-line module-swap shim at the top of the app entrypoint.
- *Note:* budget 1–2 hours for deploy friction regardless; this is exactly the class of debugging routed to **CC**.

**F5 — Week 4 is the over-scope risk (§15 asked for this check).**
- *Problem:* Brief form + 3-concept pipeline with evidence + Reviewer agent + export, at 15–25 hrs part-time *with* §16 walkthroughs, is the tightest week (est. 22–24 hrs at the low end of the range).
- *Smallest fixes, already applied below:* (a) the Reviewer's flag-rule rubric is drafted as a Chat session in Week 3's slack (W3.7, ~1 hr) so Week 4 only implements it; (b) export ships as **Markdown only** — PDF is a stretch line-item.
- *No scope is cut from the spine.*

**F6 — DeepSeek V4 (minor, informational).**
- Exists and is live as of July 2026 (`deepseek-v4-flash`); note peak/off-peak pricing above.
- No fix needed — flagged only because Instructions item 3 asks that named model versions be verified.

---

## 1. Repository structure

```
creativesignal/
├── README.md                      # Week 6: leads w/ problem, GIF, diagram, real-vs-simulated, eval table
├── implementation.md              # this file
├── pyproject.toml                 # Python 3.12; deps pinned
├── .env.example                   # ANTHROPIC_API_KEY only (retrieval needs no key)
├── Makefile                       # make ingest / annotate / index / eval / app / mcp
├── data/
│   ├── raw/
│   │   ├── tier1_adimagenet/      # downloaded snapshot (not committed; see data-governance)
│   │   ├── tier2_adcopy/          # both HF ad-copy sets, filtered to vertical
│   │   └── tier3_meta_sample.csv  # hand-curated; the provenance-rich core
│   ├── corpus.sqlite              # THREE tables: creatives (source) + annotations (derived) — §6 lineage — + runs (persisted generation outputs, added W4.6b)
│   └── chroma/                    # persistent vector index (gitignored; rebuilt by `make index`)
├── src/creativesignal/
│   ├── schema.py                  # Pydantic: Creative, Annotation, CreativeCard, TrendReport, Concept, ReviewResult
│   ├── llm.py                     # thin Claude API wrapper; model-tier constants (HAIKU_MODEL, SONNET_MODEL)
│   ├── tracing.py                 # Phoenix setup
│   ├── sources/
│   │   ├── base.py                # CreativeSource interface: .search(query, filters)  — §6, as decided
│   │   ├── curated.py             # CuratedCorpusConnector (the only one on the critical path)
│   │   └── live_stubs.py          # MetaLiveConnector / TikTokConnector: interface-conforming stubs, NotImplemented
│   ├── ingest/
│   │   ├── load_tier1.py  load_tier2.py  load_tier3.py
│   │   └── build_corpus.py        # normalize → creatives table
│   ├── annotate/
│   │   ├── taxonomy.py            # fixed hook_type / tone label sets (Week 1, frozen after bootstrap)
│   │   ├── bootstrap.py           # F2 seed-labeling pass (one-time)
│   │   ├── classical.py           # TF-IDF + LogisticRegression; predict_with_confidence()
│   │   ├── escalate.py            # low-confidence → LLM; writes to annotations table w/ annotator= field
│   │   └── report.py              # confusion matrix, precision/recall table, escalation-rate stat
│   ├── retrieval/
│   │   ├── cards.py               # creative card + analyst-summary generation (§8 two representations)
│   │   ├── index.py               # Chroma collection build (bge-small-en-v1.5) + BM25 index (rank_bm25)
│   │   └── hybrid.py              # parse filters → semantic + keyword → merge/rerank → cited results + coverage stmt
│   ├── insight/
│   │   └── tree.py                # §5 Job B decision tree on longevity proxy (F1); rules + viz export
│   ├── agents/
│   │   ├── tools.py               # search_creatives, get_creative_details, analyze_pattern, generate_concepts, run_evaluation
│   │   ├── analyst.py             # bounded loop per §9; emits structured trace
│   │   └── reviewer.py            # claim / scarcity / prohibited-language / similarity checks → ReviewResult
│   └── eval/
│       ├── golden_set.jsonl       # query → [relevant creative_ids]; 20 → 30-50
│       ├── metrics.py             # recall@5, precision@5, citation_correctness (hand-rolled, explainable)
│       ├── ragas_eval.py          # groundedness/faithfulness
│       ├── rubric.md              # human 1–5 rubric: relevance, specificity, grounding, actionability, brand safety, novelty
│       └── run_eval.py            # one command → eval/results/*.json + summary table
├── mcp_server/
│   └── server.py                  # creative-intelligence-mcp: 4 read-only tools per §9
├── app/
│   ├── streamlit_app.py           # entry; honesty footer verbatim; F4 sqlite shim at top
│   └── pages/
│       ├── 1_explore.py           # search corpus, view cards + provenance
│       ├── 2_brief_to_concepts.py # brief form → trace → evidence → 3 concepts → reviewer flags → export .md
│       ├── 3_insights.py          # tree viz, feature importance, trend report
│       └── 4_eval_dashboard.py    # results table vs. §11 targets
├── docs/
│   ├── prd.md  architecture.md  data-governance.md  eval-plan.md  case-study.md  decision-log.md
└── tests/                         # smoke tests: schema round-trip, retrieval returns citations, reviewer flags a planted claim
```

## 2. Setup (Week 0, ~1 hr of the half-day)

1. `git init`; Python 3.12 via `uv` or `pyenv`; `uv pip install -e .`
2. Dependencies (pin in `pyproject.toml`): `pydantic`, `anthropic`, `chromadb`, `sentence-transformers`, `rank_bm25`, `scikit-learn`, `pandas`, `streamlit`, `arize-phoenix`, `ragas`, `datasets` (HF), `matplotlib`, `mcp` (Python SDK), `pytest`.
3. `.env` with `ANTHROPIC_API_KEY`. No other keys on the critical path.
4. Kilo Code: set provider to DeepSeek, model `deepseek-v4-flash`; confirm one hello-world edit round-trips. Claude Code: confirm installed and authenticated.
5. `make` targets stubbed so every later week is one command to reproduce.

---

## 3. Week-by-week plan

Effort estimates assume a PM at 15–25 hrs/week with CC/KC doing the typing. **Walkthrough (§16)** rows are the decision-by-decision sessions — do them *before* the build task they precede. Every week ends with the explain-it-back checkpoint (15–30 min, never skipped — §16 fallback rule 3).

### Week 0 — Pre-work (~half day, as decided)

*Why this week:* nothing downstream is buildable without a vertical, data on disk, and licenses recorded.

| # | Task | Output | Tool | Est |
|---|---|---|---|---|
| W0.1 | One-page PRD: persona, JTBD, success metrics (= §11 targets), non-goals (= §4 cut list) | `docs/prd.md` | Chat + Human | 1.0h |
| W0.2 | Confirm vertical (default: skincare, see Section 0.1 above) — record in decision log | `docs/decision-log.md` entry #1 | Human | 0.2h |
| W0.3 | Curate Tier-3: 100–200 skincare ads from Meta Ad Library. Per record: ad-library URL, advertiser, date observed, platform, copy, category, `source_type`, `rights_note`, **plus F1 fields: start date → `days_active`, `variant_count`** | `data/raw/tier3_meta_sample.csv` | Human | 2.0h |
| W0.4 | Download Tier-1 (`PeterBrendan/AdImageNet`) + Tier-2 (`smangrul/ad-copy-generation`, `jaykin01/advertisement-copy`); copy each card's actual license into governance doc | `data/raw/…`, `docs/data-governance.md` v1 | KC (download scripts are mechanical) | 0.8h |

**Definition of done:** PRD exists; ≥100 Tier-3 rows with F1 proxy fields populated; all three datasets on disk with licenses recorded; both coding tools configured (see Section 2, step 4, above).

---

### Week 1 — Thin vertical slice + classical-ML baseline (est. 18–20h)

*Why this week (restate before starting):* an ugly end-to-end path de-risks the demo and teaches how the layers interact; the annotator starts life now so its cost story accumulates all six weeks.

| # | Task | Files / functions | Tool | Est |
|---|---|---|---|---|
| W1.1 | Repo scaffold, pyproject, Makefile, .env.example, tests skeleton | tree in Section 1 above | KC | 1.5h |
| W1.2 | **Walkthrough:** provenance schema — which fields, why source vs. annotation tables split, how each §11 metric maps to a field (this is the check that no eval metric lacks a schema field) | notes → decision log | Chat | 0.7h |
| W1.3 | Implement schema + two-table SQLite layout | `schema.py`, `ingest/build_corpus.py` | **CC** (schema design row) | 2.0h |
| W1.4 | Loaders: Tier-1/2/3 → normalized `creatives` table (~300 rows loaded: all Tier-3 + vertical-filtered Tier-2 sample) | `ingest/load_tier*.py` | KC ⚖️ *(this week's spot-check task)* | 2.5h |
| W1.5 | **Walkthrough:** freeze `hook_type` / `tone` taxonomies (6–8 labels each) — the F2 bootstrap depends on these not moving | `annotate/taxonomy.py` | Chat | 0.5h |
| W1.6 | F2 bootstrap: LLM (Haiku tier) labels ~250 Tier-2 rows; export 50-row verification sheet | `annotate/bootstrap.py` | Prompt: **CC**; batch script: KC | 1.5h |
| W1.7 | Hand-verify 50 rows, correct | corrected seed CSV | Human | 0.8h |
| W1.8 | Train TF-IDF + logistic regression; `predict_with_confidence()`; confusion matrix + P/R table | `annotate/classical.py`, `report.py` | KC (sklearn boilerplate) | 2.0h |
| W1.9 | **Walkthrough:** pick the escalation confidence threshold from the P/R table — the cost/accuracy tradeoff is the §5 Job A PM story | decision log | Chat | 0.5h |
| W1.10 | Escalation path: below-threshold → Haiku; write both annotator outputs to `annotations` with `annotator` + `confidence` fields; compute escalation rate | `annotate/escalate.py` | KC; any debugging → **CC** | 1.5h |
| W1.11 | Naive retrieval (BM25 over raw copy — deliberately naive; hybrid is Week 2's contrast) + one concept-generation prompt | `retrieval/index.py` (bm25 part), `llm.py` | Retrieval: KC (rationale: naive-by-design, no judgment yet); concept prompt: **CC** | 2.0h |
| W1.12 | Wire slice: brief string → retrieve 5 → concept w/ cited IDs → print; one manual eval note | `make slice` | **CC** (first end-to-end integration = where intent-level debugging lives) | 1.5h |
| W1.13 | ⚖️ Spot-check W1.4 output against a CC rerun; log diff | decision log | Human + both tools | 0.5h |
| W1.14 | Explain-it-back checkpoint | written or spoken | Human | 0.3h |

**Data artifacts:** populated `creatives` + `annotations` tables; corrected seed set; confusion matrix PNG; escalation-rate stat.
**Definition of done:** `make slice` runs brief→concept end-to-end with a cited ID; annotator accuracy vs. the 50 verified rows is measured (whatever it is — the *measurement* is the deliverable); escalation rate known; checkpoint done.

---

### Week 2 — Real RAG + eval harness (est. ~18h)

*Why:* the retrieval unit (card + summary, not chunks) is the product's core design claim, and the eval spine must exist before anything is worth improving.

| # | Task | Files / functions | Tool | Est |
|---|---|---|---|---|
| W2.1 | **Walkthrough:** hybrid merge/rerank logic (explicitly named in §16 as a walkthrough item): weighting semantic vs. BM25, dedupe, metadata-filter precedence | decision log | Chat | 0.7h |
| W2.2 | Creative-card builder from schema fields; analyst-summary prompt | `retrieval/cards.py` | Card assembly: KC; summary **prompt**: **CC** (judgment: it defines what's retrievable) | 2.0h |
| W2.3 | Batch-generate analyst summaries (Haiku tier) for corpus | same | KC | 1.0h |
| W2.4 | Chroma index over cards + summaries with `bge-small-en-v1.5`; metadata fields alongside | `retrieval/index.py` | KC ⚖️ | 2.0h |
| W2.5 | Hybrid pipeline per §8: parse filters → semantic + keyword → merge/rerank → results carry creative IDs + source links + coverage statement (verbatim honesty framing) | `retrieval/hybrid.py` | **CC** (architecture/judgment row) | 3.0h |
| W2.6 | Golden set: 20 realistic queries, 3–5 relevant IDs each, hand-labeled | `eval/golden_set.jsonl` | Human + Chat (query brainstorm) | 2.0h |
| W2.7 | **Walkthrough:** exact metric formulas — what counts as "relevant retrieved" for Recall@5 when an ID appears in either representation (named §16 item) | decision log | Chat | 0.5h |
| W2.8 | Metrics + runner: recall@5, precision@5; compare **semantic-only vs. hybrid** | `eval/metrics.py`, `run_eval.py` | **CC** (formulas are judgment-bearing; runner is small enough not to split) | 2.5h |
| W2.9 | Minimal explore page: search box → cited cards w/ provenance. **Also create `.streamlit/config.toml` theme and follow the "UI design direction" section of AGENTS.md** — every later page inherits both | `app/pages/1_explore.py`, `.streamlit/config.toml` | KC (standard UI) | 2.0h |
| W2.10 | ⚖️ Spot-check W2.4; log | decision log | Human | 0.5h |
| W2.11 | Checkpoint | — | Human | 0.3h |

**Definition of done:** "find offer-led skincare ads" returns cited cards in the UI; `make eval` prints semantic-vs-hybrid Recall@5/Precision@5 (record the numbers even if below the 0.70 target — trend line starts now); checkpoint done.

---

### Week 3 — Intelligence layer: analyst agent + interpretable insight (est. ~20h)

*Why:* retrieval becomes a product when an agent turns questions into traceable, cited reports; the tree turns the corpus into interpretable claims that stay inside the honesty guardrail.

| # | Task | Files / functions | Tool | Est |
|---|---|---|---|---|
| W3.1 | **Walkthrough:** agent loop bounds — max tool calls, when it asks a clarifying question, what triggers the coverage check | decision log | Chat | 0.7h |
| W3.2 | Tool layer: the five §9 tools as plain functions wrapping existing modules | `agents/tools.py` | KC (wrappers are mechanical) ⚖️ | 1.5h |
| W3.3 | Creative Analyst agent: interpret brief → filters → retrieve → coverage check → synthesize w/ citations → self-check claims vs. sources → clarify if brand constraints missing; structured trace object at every step | `agents/analyst.py` | **CC** (agent workflow design row) | 4.0h |
| W3.4 | Phoenix tracing wired through LLM + tool calls | `tracing.py` | KC | 1.0h |
| W3.5 | **Walkthrough:** decision-tree feature set (named §16 item) — which schema fields become features; confirm F1 `proxy_bucket` as label; depth cap for interpretability | decision log | Chat | 0.7h |
| W3.6 | §5 Job B tree on Tier-3: train, extract rules as sentences, tree viz + feature-importance chart; every output sentence carries the descriptive-not-causal framing | `insight/tree.py` | Training/viz: KC; **rule-to-sentence wording**: **CC** (honesty language is judgment) | 2.5h |
| W3.7 | (F5 prep) Draft Reviewer flag-rule rubric: unsupported efficacy/health claims, false scarcity, prohibited targeting language, similarity threshold — rules only, no code | rubric → decision log | Chat | 1.0h |
| W3.8 | Trend-report template: patterns, counter-examples, confidence, coverage statement; agent fills it | `schema.py` TrendReport, `agents/analyst.py` | **CC** | 1.5h |
| W3.9 | Insights page: tree viz, importance chart, generate-trend-report button w/ visible trace | `app/pages/3_insights.py` | KC | 2.0h |
| W3.10 | Grow golden set +5 queries targeting the new trend-report path; rerun eval | `eval/` | Human | 1.0h |
| W3.11 | ⚖️ Spot-check W3.2; log | decision log | Human | 0.5h |
| W3.12 | Checkpoint | — | Human | 0.3h |

**Definition of done:** a question typed into the insights page becomes a cited trend report with a visible plan→tools→evidence→output trace in Phoenix and in the UI; tree rules render with descriptive framing; checkpoint done.

---

### Week 4 — Full workflow + reviewer (est. 22–24h — flagged F5 as the tightest week; watch §16 fallback rule 1)

*Why:* this is the demo's money path — brief in, reviewable evidence-backed concepts out, with an independent policy check mirroring real ad-tech.

| # | Task | Files / functions | Tool | Est |
|---|---|---|---|---|
| W4.1 | Brief form: audience, objective, tone, prohibited claims | `app/pages/2_brief_to_concepts.py` | Mockup: Chat (Artifacts, per F3); implementation: KC (standard UI) | 2.0h |
| W4.2 | **Walkthrough:** what makes 3 concepts *distinct* (pattern-diversity constraint) and what "why this concept" evidence must contain | decision log | Chat | 0.7h |
| W4.3 | Concept pipeline: brief → analyst agent → 3 distinct concepts, each with cited evidence block | `agents/analyst.py` extension, `schema.py` Concept | **CC** | 3.5h |
| W4.4 | **Walkthrough:** reviewer flagging rules finalized from W3.7 draft (named §16 item); set the similarity threshold against retrieved ads | decision log | Chat | 0.5h |
| W4.5 | Reviewer agent: claim check, scarcity check, prohibited-language check, similarity-vs-retrieved check → structured `ReviewResult` with per-flag evidence | `agents/reviewer.py` | **CC** (judgment + responsible-AI row) | 3.5h |
| W4.6 | Wire draft→review loop into the page: concepts render with reviewer flags inline; accept/edit affordance | page 2 | KC; integration debugging → **CC** ⚖️ | 2.5h |
| W4.6b | Persist every generation run to a `runs` table: `run_id`, timestamp, brief (JSON), retrieved creative IDs, trend report, concepts (JSON), `ReviewResult`, model + prompt versions, token cost. Written automatically at the end of every brief→concepts run; page 2 gets a "past runs" list | `schema.py` Run model, `agents/analyst.py` hook | KC (rationale: the models exist; this is a write-through + list view — mechanical) | 1.5h |
| W4.7 | Export to Markdown (PDF = stretch, per F5) | `export.py` | KC | 1.0h |
| W4.8 | Golden set +5 (brief-shaped queries); add **citation-correctness** metric per §11; rerun | `eval/metrics.py` | **CC** (new metric formula) | 1.5h |
| W4.9 | Planted-violation test: a brief with a prohibited claim must get flagged (this becomes the demo beat) | `tests/test_reviewer.py` | KC | 0.8h |
| W4.10 | ⚖️ Spot-check W4.6; log | decision log | Human | 0.5h |
| W4.11 | Checkpoint | — | Human | 0.3h |

**Definition of done:** brief → evidence → 3 distinct cited concepts → reviewer flags the planted issue → export .md, all in the UI; citation correctness measured; checkpoint done. **If this week slips >3 days:** invoke §16 fallback rule 1 — nothing here is cuttable (all spine), so pull hours from Week 5's golden-set expansion, not from walkthroughs.

---

### Week 5 — Differentiator (MCP) + eval depth (est. ~20h)

*Why:* MCP proves the product's tool layer is interoperable — same corpus, queried from the app and from a coding agent; eval depth is what makes the README's results table credible.

| # | Task | Files / functions | Tool | Est |
|---|---|---|---|---|
| W5.1 | **Walkthrough:** MCP tool contracts — inputs/outputs for `search_creatives`, `get_creative_details`, `get_category_stats`, `generate_evidence_report`; read-only guarantee | decision log | Chat | 0.7h |
| W5.2 | MCP server implementation (Python `mcp` SDK, stdio transport) wrapping the existing tool layer | `mcp_server/server.py` | **KC — per routing table** (interoperability lesson: built from a different tool than designed the app; doubles as the live cost/quality comparison) | 3.5h |
| W5.3 | Validate as a client: register the server in **Kilo Code's** MCP config, run all four tools against real queries, save transcripts | `docs/` transcript snippets | **KC — per routing table** | 1.5h |
| W5.4 | **Escalation lane (pre-authorized per the table's exception):** any JSON-RPC handshake, tool-schema mismatch, or client/server contract failure in W5.2–W5.3 moves that specific debugging to **CC**, then returns to KC | — | **CC** on trigger | (1.5h buffer) |
| W5.5 | Bonus demo beat: also register the server in Claude Code and run one query — same corpus, two different clients (30 min, pure demo value) | screenshot for README | CC (as client) | 0.5h |
| W5.6 | Expand golden set to 30–50 queries | `eval/golden_set.jsonl` | Human + Chat | 2.5h |
| W5.7 | Ragas groundedness/faithfulness over a sample of generated reports/concepts | `eval/ragas_eval.py` | KC ⚖️ | 1.5h |
| W5.8 | Human rubric eval: recruit 3–5 people, each scores a fixed output set 1–5 on the six §11 dimensions; collect. **Rubric must include written score anchors** — a one-sentence definition of 1, 3, and 5 for each dimension (e.g., grounding: 1 = claims with no citation; 3 = cited but citation only partially supports; 5 = every claim fully supported by its citation) so raters share a scale. **The fixed set is drawn from the `runs` table (W4.6b)** — stable run IDs mean every scorer rates identical outputs and results are re-traceable later | `eval/rubric.md`, results CSV | Human | 3.0h |
| W5.9 | **Walkthrough (Chat, per §16 "use Claude for judgment"):** interpret full results vs. §11 targets — what's below target, why, fix-vs-disclose | decision log + `docs/eval-plan.md` | Chat | 1.0h |
| W5.10 | Eval dashboard page: results vs. targets, semantic-vs-hybrid history, escalation-rate + annotator table from Week 1, sample sizes, "directional" label | `app/pages/4_eval_dashboard.py` | KC | 2.0h |
| W5.10b | *(Stretch — first thing to skip if tight; sits behind existing stretch items in the cut order)* Corpus health panel folded into the explore page: record counts by tier/source, `hook_type`/`tone` label distributions, LR-vs-LLM escalation rate, `rights_note` coverage %. Makes the data-governance story visible in the demo | `app/pages/1_explore.py` addition | KC (stats readout — boilerplate row) | 1.5h |
| W5.11 | ⚖️ Spot-check W5.7; log — and write the summary paragraph on the whole KC-vs-CC experience for the case study | decision log | Human | 0.7h |
| W5.12 | Checkpoint | — | Human | 0.3h |

**Definition of done:** MCP server answers all four tools from Kilo Code (and the Claude Code bonus query); golden set ≥30 with human-eval results in; dashboard shows the full §11 table with sample sizes; checkpoint done. Fine-tune remains unscheduled stretch — its §10 kill-switch means it only enters if Weeks 1–4 banked surplus, and it exits after 2 days regardless.

---

### Week 6 — Recruiter-ready polish (est. ~15h)

*Why:* per §14, judgment artifacts are the real deliverable; a grader/recruiter must reproduce and grasp the project in minutes.

| # | Task | Output | Tool | Est |
|---|---|---|---|---|
| W6.1 | Deploy to Streamlit Community Cloud with bundled Chroma. API key goes in **Streamlit Cloud's Secrets settings** (read via `st.secrets`), never in the repo — verify `.env` and `.streamlit/secrets.toml` are gitignored before first push | live URL | KC (config) | 1.5h |
| W6.1b | **Demo mode (default on the deployed app).** The public app replays persisted runs from the `runs` table: brief form is pre-filled from a saved run, "Generate" loads the stored trend report, concepts, and reviewer flags instantly — no API call. A "Live mode" toggle prompts for a password (checked against `st.secrets["demo_password"]`) before any real LLM call is possible. Locally (no deploy secrets present), live mode is simply on. Protects your API credits from strangers/bots hitting a public URL, and makes the recruiter's first click instant instead of a 30-second agent spinner | `app/streamlit_app.py` mode gate, page 2 | KC (mode gate is mechanical; the `runs` replay path already exists from W4.6b) | 1.5h |
| W6.2 | F4 fix pre-applied (`pysqlite3-binary` + shim); any deploy failures | — | **CC** (debugging row) | 1.5h |
| W6.3 | Architecture diagram | draft in Chat (Artifacts, per F3) → final SVG/PNG in README | Chat + Human | 1.5h |
| W6.4 | README: one-sentence problem, 30-sec GIF, diagram, real-vs-simulated, §11 results table, licensing constraints, limitations | `README.md` | Chat draft + Human edit | 2.5h |
| W6.5 | Case study incl. "what I'd do with production data" + the model-routing/cost-tier findings from the ⚖️ log | `docs/case-study.md` | Chat + Human | 2.5h |
| W6.6 | Finalize architecture/eval-plan/data-governance docs; decision log cleanup | `docs/` | Chat + Human | 2.0h |
| W6.7 | 3–5 min demo video following the §14 single narrative (brief → agent plan → evidence → trend report → concepts → reviewer flag → eval panel → MCP query from Kilo Code) | video | Human | 2.5h |
| W6.8 | Final checkpoint: the full interview run-through | notes | Human | 0.5h |

**Definition of done:** public URL works from a clean browser; README complete per §14; video recorded; all six docs final; you can deliver the demo narrative unscripted.

---

## 4. V0 / stretch splits for the four riskiest tasks

Ship the V0; upgrade to stretch only if the week has slack. **V0 alone satisfies every spine requirement** — the stretch column is polish, not completion.

| Task | V0 (ship this) | Stretch (only with slack) |
|---|---|---|
| W2.5 Hybrid retrieval | Weighted score fusion: normalize semantic + BM25 scores, weighted sum, metadata filters as hard pre-filter | Add a rerank pass (LLM-as-reranker over top-15, or cross-encoder) and measure whether it moves Recall@5 |
| W3.3 Analyst agent | Fixed pipeline that calls the five tools in a set order with coverage check + structured trace | Dynamic behavior: agent decides tool order and asks the clarifying question when brand constraints are missing |
| W4.5 Reviewer agent | Two checks: unsupported efficacy/health claims + similarity-vs-retrieved (the two that create demo moments) | All four checks (add false scarcity + prohibited targeting language) |
| W5.10 Eval dashboard | Static results table vs. §11 targets with sample sizes | Metric history across weeks (semantic-vs-hybrid trend line, escalation-rate over time) |

W4.7 export was already split this way (V0 = Markdown; stretch = PDF).

## 5. Learning additions (small, deliberate — do not skip these to save time)

| # | Addition | Where it lands | Est |
|---|---|---|---|
| L1 | **Failure reading.** After each eval run (W2.8, W4.8, W5.9): open the 10 worst retrieval failures, categorize each (wrong filter parse / vocabulary mismatch / label error / genuinely ambiguous query), one paragraph in the decision log. The categories, not the metric, tell you what to fix next — this is the core eval skill. | Weeks 2, 4, 5 | +45 min each |
| L2 | **Cost log.** `eval/cost_log.csv`: for each annotation path (LR vs. LLM-escalated) and each agent run, record tokens × published price. Makes the Job A claim ("cut annotation cost by X") a real number in the case study instead of an estimate. Implementation: ~20 lines in `llm.py`. | Built W1.10 (KC), read weekly | +30 min once |
| L3 | **One measured prompt A/B.** In Week 4 or 5, pick one prompt change you'd make anyway (e.g., the analyst-summary prompt), version it (`prompts/summary_v1.txt`, `_v2.txt`), re-run retrieval eval before/after, log the delta. Teaches "prompts are product changes you measure." | Week 4 or 5 slack | +1 h once |

## 6. Handing tasks to Claude Code / Kilo Code (how to actually run this)

`implementation.md` is the plan; agents also need **standing project context** so you don't re-explain the project every session and so their output doesn't drift toward generic-tutorial patterns the plan rejects.

**File setup (verified against both tools' current docs, July 2026):** the project context lives in **`AGENTS.md`** at repo root — Kilo Code reads it automatically (its old memory-bank feature is deprecated in favor of AGENTS.md, and the file is write-protected in Kilo so the agent can't silently edit its own rules). Claude Code does **not** read AGENTS.md; it reads `CLAUDE.md` — so `CLAUDE.md` is a two-line stub containing the import `@AGENTS.md` (Claude Code expands imports at session start) plus any Claude-Code-only notes. One source of truth, zero drift, no `.kilocode/memory-bank/` needed.

Per-task kickoff pattern (works in both tools):

> "Read CLAUDE.md, then task **W2.4** in implementation.md. Build exactly that task's files. Stop when its output line is satisfied; don't expand scope."

Rules of the road:
- **One task ID per agent session.** Multi-task sessions are where scope creep and silent decisions happen.
- **Walkthrough tasks (Chat) always precede their build task** — paste the decision-log conclusion into the build prompt so the agent implements *your* decision, not its own.
- **The agent proposes, you commit.** Review the diff before accepting; if you can't explain a diff, that's a §16 signal to ask why before merging.
- **Debugging that exceeds ~2 KC attempts moves to CC** (the table's bug-fixing row) — don't let the cheap backend thrash.

## 7. Standing rules during execution (binding, from §16)

1. **Cut order if slipping:** fine-tune → A2A → image drafts → MCP. Never eval, never the analyst/reviewer loop.
2. **First response to slipping is scope, not learning time.** Walkthroughs shrink to 5-minute versions before they disappear; checkpoints never disappear.
3. **>1 week behind at start of Week 4 → stop and re-cut explicitly** against the spine list in this file's Section 4 (V0/stretch splits); update this file rather than letting weeks silently compress.
4. **Tool routing is fixed, with bounded discretion:** ambiguous tasks get a one-line inline rationale (as done above for W1.11, W2.2, W2.8, W3.6), never a silent default. If you notice several tasks in a row executed without a "why," invoke the fallback consciously.
5. **Every ⚖️ spot-check lands in `docs/decision-log.md`** — five paragraphs by Week 5 is the raw material for the case study's model-selection section.
