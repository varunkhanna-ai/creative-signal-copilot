# CreativeSignal — Product Requirements (One-Pager)

## Persona

**Freelance / solo skincare marketer** managing multiple client accounts. No in-house creative team, no internal legal/compliance function to catch problems before an ad goes live. Works fast, across several brands at once, and is personally on the hook if a client's ad gets rejected or flagged by a platform for an unsupported efficacy claim.

## Job to be Done

*When I'm preparing a new ad campaign for a skincare client, I want to quickly see evidence-backed patterns from real skincare ads and get reviewable concept drafts with policy risk flagged automatically, so I can move fast and catch problems myself — since I don't have an internal team to catch them for me.*

This framing is why the Reviewer agent isn't a nice-to-have double-check — for this persona, it *is* the compliance function. There is no one else.

## Success Metrics (§11 targets — fixed by the strategy doc, not re-litigated here)

| Metric | What it catches |
|---|---|
| Recall@5 / Precision@5 (~0.70 target) | Retrieval quality — the foundation everything else depends on |
| Citation-correctness | Whether a generated claim's citation actually supports it (operationalizes the honesty rule) |
| Ragas groundedness/faithfulness | Whether generated text is grounded in evidence vs. hallucinated |
| Human rubric, 6 dimensions (relevance, specificity, grounding, actionability, brand safety, novelty), 1–5 with written anchors | Perceived usefulness — what no automated metric can judge |
| Annotator escalation rate (LR vs. LLM) | Cost efficiency of the annotation pipeline |

*(Deeper design discussion on these — thresholds, formulas, what "relevant" means for Recall@5 — deferred to the W1.2/W2.6–2.8 walkthroughs where they're actually implemented, not resolved in the abstract here.)*

## Non-Goals

**Cut order if time runs short:** fine-tune → A2A → image drafts → MCP. Never eval, never the analyst/reviewer loop — those are the spine.

**Permanently out of scope regardless of time:**
- Live scraping or live API calls to Meta/TikTok (curated local corpus only)
- Cloud databases or any vendor API key beyond `ANTHROPIC_API_KEY`
- Document chunking (retrieval unit is a structured creative record, not text chunks)
- Any agent framework (LangChain/LlamaIndex/CrewAI) — plain Python + Pydantic only
- Causal/performance claims in any output — descriptive/proxy language only, per the honesty rule
