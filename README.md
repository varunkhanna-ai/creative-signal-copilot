# CreativeSignal

**Marketers guess which creative direction to try next. CreativeSignal turns a campaign brief into ad concepts that cite the real ads they were derived from — and flags its own policy risks before a human sees them.**

> Every insight is traceable to examples; every recommendation is a hypothesis, not a performance claim.

That line is not marketing copy. It is enforced in code: concepts citing evidence they were not given are **dropped, not flagged**; insight rules are rendered through a function that a test forbids from emitting performance language; and the eval dashboard shows "not yet measured" rather than a zero.

---

## Status: honest read

This is a 6-week AI-PM capstone. The architecture is complete and tested end to end. **The corpus is not.**

| | State |
|---|---|
| Retrieval, agent, reviewer, MCP server, 4-page app | Built, tested, running |
| Test suite | 214 passing |
| Corpus | **9 synthetic ads** — Tier-3 curation outstanding |
| Retrieval eval numbers | **None published** — no golden set, corpus too small to measure |
| Insight tree | Built and unit-tested; **never trained on real data** |
| LLM generation paths | Built; **not executed** (no API key at build time) |

Nothing here is a placeholder number. Where a measurement does not exist, the app, the docs, and this README say so and name the task that would produce it. The reasoning behind every gap is in [`docs/decision-log.md`](docs/decision-log.md) under **BLOCKERS**.

---

## What is real vs. simulated

**Real:**
- The retrieval pipeline — Chroma + `bge-small-en-v1.5` + BM25, hybrid fusion, running locally on the actual corpus with no API key.
- The reviewer's four policy checks — fully deterministic, no LLM, verifiable.
- The MCP server — four read-only tools, validated over real stdio JSON-RPC ([transcript](docs/mcp-transcript.md)).
- The two-table lineage (`creatives` / `annotations`) and the third `runs` table.

**Simulated or absent:**
- **The corpus.** Nine synthetic ads from two Hugging Face ad-copy datasets, all following one generated template. No provenance, no ad-library links, no longevity data.
- **Performance data.** There is none, anywhere, by design — the Meta Ad Library exposes no engagement metrics for ordinary commercial ads. The insight model's label is an *ad-longevity proxy* (`days_active`, `variant_count`), which is a spend-persistence signal, not a performance measurement.
- **All eval numbers.** Not computed, not estimated, not published.

---

## Architecture

```
Brief
  │
  ▼
Analyst agent (plain Python, fixed pipeline, bounded)
  │  interpret → filters → retrieve → coverage check → prevalence → synthesize → self-check
  ▼
Hybrid retrieval ──────────────┐
  │  semantic (Chroma/bge)     │  ← two representations per creative (§8), never chunks:
  │  keyword  (BM25)           │     the creative card + an LLM analyst summary
  │  weighted fusion, deduped  │
  ▼                            │
Evidence (cited creative IDs) ─┘
  │
  ├──▶ Trend report  → patterns as prevalence counts + coverage statement
  └──▶ 3 concepts    → citation self-check → Reviewer agent (4 deterministic checks)
                                                   │
                                                   ▼
                                          runs table → replay / export / human eval

corpus.sqlite:  creatives (source)  |  annotations (derived)  |  runs (generated)
                        ↑ never merged — §6 lineage
```

The same tool layer is exposed twice: to the Streamlit app, and over MCP to any coding agent.

---

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
make download && make ingest && make index
make app
```

Retrieval runs with **no API key**. Only generation needs one:

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
```

| Target | Does |
|---|---|
| `make download` | Snapshot the Hugging Face datasets to `data/raw/` |
| `make ingest` | Normalize all tiers into `creatives` |
| `make annotate` | F2 bootstrap seed-labeling pass (needs a key) |
| `make summaries` | Batch-generate analyst summaries (needs a key) |
| `make index` | Build the Chroma + BM25 indexes |
| `make slice` | The W1.12 end-to-end path, brief → concept |
| `make eval` | Retrieval eval: keyword vs. semantic vs. hybrid |
| `make app` | Streamlit app |
| `make mcp` | MCP server over stdio |
| `make test` | 214 tests |

---

## Design decisions worth reading

The [decision log](docs/decision-log.md) is the real deliverable of a PM capstone. A few that shaped the build:

- **[#3] `creatives` vs. `annotations`** — the split rule is "did a model exercise judgment," not "was this computed."
- **[#7] The corpus is 9 rows, not 24** — reading the actual rows (not the row count) exposed a 17% false-positive rate in the vertical filter and near-total overlap between two supposedly independent datasets.
- **[#11] Recall@5 counts creative IDs, not representations** — otherwise the two-representation design inflates its own score against the baseline it is compared to.
- **[#12] A segfault, diagnosed from the macOS crash report** — the plausible guess (PyTorch) was wrong; the actual cause was PyArrow's mimalloc allocator. Would have killed the deployed app on the first search.
- **[#16] BM25's IDF goes negative on common terms** — filtering on `score > 0` silently dropped valid matches, and the bug got *worse* as the corpus got smaller.
- **[#17] Tree features exclude `days_active` and `variant_count`** — they *are* the label, so including them would produce ~100% accuracy that means nothing.
- **[#20] No relevance floor on vector search** — measured, documented, and deliberately not "fixed" with an uncalibrated threshold.

---

## Limitations

1. **The corpus is the bottleneck, and everything downstream inherits it.** Nine synthetic ads following one template. Every ad contains "Limited stock," so the reviewer's false-scarcity check flags 100% of them — a corpus artifact the flag text says out loud.
2. **No performance data exists, and none is simulated.** The longevity proxy is the honest substitute, and it is labeled as a proxy everywhere it appears — including inside the embedded index text.
3. **Two thresholds are uncalibrated placeholders** — the escalation confidence (0.70) and the proxy buckets (90 days / 5 variants). Both are flagged in the decision log as pending real data, with the procedure for setting them written down.
4. **Tier-1 (AdImageNet) is gated** on Hugging Face and is not in the corpus.
5. **Licensing constrains redistribution.** Two of the three source datasets declare no usable license, so Tier-2 text is used locally and never republished — see [`docs/data-governance.md`](docs/data-governance.md).

---

## Stack

Python 3.12 · Pydantic · ChromaDB · `sentence-transformers` (`BAAI/bge-small-en-v1.5`) · `rank_bm25` · scikit-learn · Anthropic API · Streamlit · Phoenix · Ragas · Python `mcp` SDK.

No LangChain, no LlamaIndex, no agent framework — agents are plain Python loops with Pydantic-typed tools, so every step is inspectable and explainable.
