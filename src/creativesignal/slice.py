"""W1.12: the thin end-to-end slice. brief -> retrieve 5 -> concept -> print.

Deliberately ugly and linear. Its job is to prove the layers connect and to
be the thing Week 2's real retrieval measurably improves on — not to be the
product. The agent loop that replaces it is W3.3.

    make slice
    make slice BRIEF="hydrating serum for sensitive skin"
"""

from __future__ import annotations

import argparse
import json

from creativesignal.llm import SONNET_MODEL, complete, has_api_key, load_prompt
from creativesignal.schema import Concept, coverage_statement
from creativesignal.sources.base import SearchResult
from creativesignal.sources.curated import CuratedCorpusConnector

DEFAULT_BRIEF = "hydrating serum for sensitive skin, dermatologist-backed tone"
PROMPT_NAME = "concept_v1"
N_RETRIEVE = 5
N_CONCEPTS = 3


def format_evidence(results: list[SearchResult]) -> str:
    """Render retrieved creatives for the prompt, ids attached to every block.

    The id must sit next to the text it labels — that adjacency is what lets
    the model cite accurately and what makes a wrong citation detectable.
    """
    blocks = []
    for result in results:
        creative = result.creative
        blocks.append(
            f"[{creative.creative_id}] (score {result.score:.2f}, "
            f"via {result.retrieved_by})\n"
            f"  Advertiser: {creative.advertiser}\n"
            f"  Headline: {creative.headline or '(none)'}\n"
            f"  Body: {creative.body_copy or '(none)'}"
        )
    return "\n\n".join(blocks)


def parse_concepts(text: str) -> list[Concept]:
    """Parse the model's JSON array into Concepts, dropping uncited ones."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1].removeprefix("json").strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return []

    concepts = []
    for item in payload if isinstance(payload, list) else []:
        try:
            concept = Concept.model_validate(item)
        except Exception:
            continue
        # The honesty rule as a hard gate, not a suggestion: an uncited
        # concept is dropped rather than shown with a caveat.
        if concept.is_cited:
            concepts.append(concept)
    return concepts


def run_slice(brief: str = DEFAULT_BRIEF, limit: int = N_RETRIEVE) -> None:
    source = CuratedCorpusConnector()
    results = source.search(brief, limit=limit)

    print(f"BRIEF: {brief}\n")
    print(f"RETRIEVED ({len(results)}):")
    if not results:
        print(
            "  Nothing retrieved. The corpus is 9 rows (docs/decision-log.md B2) "
            "and BM25 needs literal term overlap — try wording closer to the ads."
        )
        return
    for result in results:
        creative = result.creative
        print(f"  [{creative.creative_id}] {creative.headline} (bm25 {result.score:.2f})")
    print()

    if not has_api_key():
        print(
            "No ANTHROPIC_API_KEY — stopping before generation.\n"
            "Retrieval above ran with no key, as required (§7). Concept "
            "generation needs one: put it in .env at the repo root."
        )
        return

    prompt = load_prompt(PROMPT_NAME).format(
        brief=brief,
        n_examples=len(results),
        evidence=format_evidence(results),
        n_concepts=N_CONCEPTS,
    )
    response = complete(
        prompt,
        task="slice_concepts",
        model=SONNET_MODEL,
        prompt_version=PROMPT_NAME,
        max_tokens=2000,
    )
    concepts = parse_concepts(response.text)

    print(f"CONCEPTS ({len(concepts)}):\n")
    retrieved_ids = {r.creative_id for r in results}
    for i, concept in enumerate(concepts, start=1):
        print(f"  {i}. {concept.title}  [{concept.hook_type or 'hook unspecified'}]")
        print(f"     {concept.headline}")
        print(f"     {concept.body_copy}")
        print(f"     Rationale: {concept.rationale}")
        # A cited id that wasn't retrieved is a hallucinated citation — the
        # exact failure the citation-correctness metric formalizes (W4.8).
        unknown = [cid for cid in concept.cited_creative_ids if cid not in retrieved_ids]
        flag = f"  <-- NOT IN RETRIEVED SET: {unknown}" if unknown else ""
        print(f"     Cites: {', '.join(concept.cited_creative_ids)}{flag}\n")

    print(coverage_statement(len(results)))
    print(f"\ncost: ${response.cost_usd:.4f} | {response.total_tokens} tokens")


def main() -> None:
    parser = argparse.ArgumentParser(description="W1.12 end-to-end slice")
    parser.add_argument("--brief", default=DEFAULT_BRIEF)
    parser.add_argument("--limit", type=int, default=N_RETRIEVE)
    args = parser.parse_args()
    run_slice(args.brief, args.limit)


if __name__ == "__main__":
    main()
