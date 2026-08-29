# CreativeSignal

**Marketers guess which creative direction to try next. CreativeSignal turns a campaign brief into ad concepts that cite the real ads they were derived from — and flags its own policy risks before a human sees them.**

> Every insight is traceable to examples; every recommendation is a hypothesis, not a performance claim.

That line is not marketing copy. It is enforced in code: concepts citing evidence they were not given are **dropped, not flagged**; insight rules are rendered through a function that a test forbids from emitting performance language; and the eval dashboard shows "not yet measured" rather than a zero.

---

## Status: honest read

This is a 6-week AI-PM capstone. The architecture is complete and tested end to end. The corpus is now real. **One blocker remains: the retrieval golden set.**

| | State |
|---|---|
| Retrieval, agent, reviewer, MCP server, 4-page app | Built, tested, running |
| Test suite | 222 passing |
| Corpus | **104 creatives** — 95 real Meta Ad Library rows (Tier-3) + 9 synthetic (Tier-2) |
| Retrieval eval numbers (Recall@5, Precision@5) | **Still blocked** — no golden set (W2.6, human-labeled relevance judgments) |
| Citation correctness | **Measured: 1.000**, n=15 concepts, across 6 real generation runs |
| Ragas answer relevancy | **Measured: 0.57–0.63**, n=15, across 2 runs |
| Ragas faithfulness | **Measured, not usable** — parser incompatibility scored only 0–3 of 15 samples |
| Insight tree | **Trained on 95 real rows** — 3 balanced longevity-proxy buckets |
| LLM generation paths | **Executed for real** — $0.535 total logged spend |

Nothing here is a placeholder number. Where a measurement does not exist, the app, the docs, and this README say so and name the task that would produce it. The reasoning behind every gap — resolved or open — is in [`docs/decision-log.md`](docs/decision-log.md) under **BLOCKERS**.

---

## What is real vs. simulated

**Real:**
- The retrieval pipeline — Chroma + `bge-small-en-v1.5` + BM25, hybrid fusion, running on the real 104-creative corpus and 208-document index, no API key required.
- The reviewer's four policy checks — fully deterministic, no LLM, verifiable, including a real planted-violation pass.
- The MCP server — four read-only tools, validated over real stdio JSON-RPC ([transcript](docs/mcp-transcript.md)).
- The two-table lineage (`creatives` / `annotations`) and the third `runs` table, holding 6 real end-to-end generations.
- 95 curated Meta Ad Library ads with real advertisers, ad-library URLs, and observed run durations.
- The insight tree, trained on real data — 95 rows, 3 balanced proxy buckets.
- Generation: 98 bootstrap labels, 5 escalations, 104 analyst summaries, 6 concept-generation runs, all against the live Claude API.

**Still absent:**
- **The retrieval golden set** (W2.6) — 20+ hand-labeled queries with known-relevant creative IDs. This is the one input every remaining unmeasured number depends on.
- **Performance data.** There is none, anywhere, by design — the Meta Ad Library exposes no engagement metrics for ordinary commercial ads. The insight model's label is an *ad-longevity proxy* (`days_active`), which is a spend-persistence signal, not a performance measurement.
- **The 9 Tier-2 rows are still synthetic** — generated ad copy with no advertiser or ad-library link, kept in the corpus for breadth but not for provenance.

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
| `make test` | 222 tests |

---

## Design decisions worth reading

The [decision log](docs/decision-log.md) is the real deliverable of a PM capstone. A few that shaped the build:

- **[#3] `creatives` vs. `annotations`** — the split rule is "did a model exercise judgment," not "was this computed."
- **[#7] Tier-2 collapsed from 24 to 9 rows** — reading the actual rows (not the row count) exposed a 17% false-positive rate in the vertical filter and near-total overlap between two supposedly independent datasets.
- **[#11] Recall@5 counts creative IDs, not representations** — otherwise the two-representation design inflates its own score against the baseline it is compared to.
- **[#12] A segfault, diagnosed from the macOS crash report** — the plausible guess (PyTorch) was wrong; the actual cause was PyArrow's mimalloc allocator. Would have killed the deployed app on the first search.
- **[#16] BM25's IDF goes negative on common terms** — filtering on `score > 0` silently dropped valid matches, and the bug got *worse* as the corpus got smaller.
- **[#23] `variant_count` turned out to be a constant** — 20 across all 95 real Tier-3 rows. It carried zero information and, under the original rule, forced every ad into the same longevity bucket; recalibrated on `days_active` alone.
- **[#26] The escalation threshold was badly wrong, and only real data showed it** — 0.70 (the honest placeholder) escalated 93–98% of real rows, collapsing the two-stage annotator into "always call the LLM." Recalibrated to 0.35 against the real out-of-fold accuracy table.
- **[#30] Getting one real, defensible Ragas number took two dependency fixes and two bug layers** — Ragas defaults to a second vendor's LLM by default, and a `temperature` incompatibility with Sonnet 5 was injected two call-layers deep inside Ragas's own code, not where the constructor argument lived. One of the two Ragas metrics still doesn't work with Claude's output format, and is reported as broken rather than silently skipped.

---

## Limitations

1. **The retrieval golden set doesn't exist.** Recall@5, Precision@5, and the semantic-vs-hybrid comparison are wired against the real 104-creative corpus and will run the moment 20+ hand-labeled queries exist — no golden set was approximated from the corpus itself to unblock this, since that would be circular.
2. **Ragas faithfulness doesn't work with Claude's output format in this ragas version.** Diagnosed to a specific parser incompatibility (its NLI-statement prompt fails to parse Claude's output on most calls) and reported as broken rather than patched further or silently omitted. `answer_relevancy`, the other Ragas metric, works reliably.
3. **The Tier-2 synthetic ads are near-duplicate template text.** The 9 rows follow one generated pattern, and every one contains "Limited stock," so the reviewer's false-scarcity check flags all of them — a corpus artifact the flag text says out loud. They remain in the corpus for breadth, not for provenance.
4. **No performance data exists, and none is simulated.** The longevity proxy is the honest substitute, computed from real Meta Ad Library run durations, and it is labeled as a proxy everywhere it appears — including inside the embedded index text.
5. **One proxy input turned out to be unusable.** `variant_count` is a constant 20 across all 95 real curated rows — likely a scrape artifact — so the longevity-proxy bucket rule now runs on `days_active` alone. Recorded, not hidden, in case real per-ad variant counts can be recovered later.
6. **Tier-1 (AdImageNet) is gated** on Hugging Face and is not in the corpus.
7. **Licensing constrains redistribution.** Two of the three Tier-2 source datasets declare no usable license, so that text is used locally and never republished — see [`docs/data-governance.md`](docs/data-governance.md). The real Tier-3 data carries its own per-record `rights_note`.

---

## Stack

Python 3.12 · Pydantic · ChromaDB · `sentence-transformers` (`BAAI/bge-small-en-v1.5`) · `rank_bm25` · scikit-learn · Anthropic API · Streamlit · Phoenix · Ragas · Python `mcp` SDK.

No LangChain, no LlamaIndex, no agent framework — agents are plain Python loops with Pydantic-typed tools, so every step is inspectable and explainable.
