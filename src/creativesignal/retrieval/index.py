"""W2.4: the Chroma vector index plus the BM25 keyword index.

One Chroma collection holds both representations (§8). Each document's id is
`{creative_id}::{representation}`, so a creative can be embedded twice while
every hit still resolves back to one record — the dedupe rule in Entry #10.

`BAAI/bge-small-en-v1.5` is the only embedding model in the project, here and
everywhere. Local, CPU, no API key: retrieval must run with no key at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from creativesignal.schema import CreativeCard

CHROMA_DIR = Path("data/chroma")
COLLECTION_NAME = "creatives"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

CARD = "card"
SUMMARY = "summary"

# Metadata keys mirrored onto every document for Chroma-side filtering.
METADATA_FIELDS = ("advertiser", "platform", "hook_type", "tone", "proxy_bucket")


def document_id(creative_id: str, representation: str) -> str:
    return f"{creative_id}::{representation}"


def parse_document_id(doc_id: str) -> tuple[str, str]:
    creative_id, _, representation = doc_id.rpartition("::")
    return creative_id, representation


@dataclass
class IndexedHit:
    """One raw vector hit, before dedupe to creative level."""

    creative_id: str
    representation: str
    score: float  # cosine similarity in [0, 1]; higher is closer


def _embedding_function():
    """bge-small via Chroma's sentence-transformers wrapper.

    Imported lazily — loading the model costs a few seconds and the CLI paths
    that never search shouldn't pay it.
    """
    from chromadb.utils import embedding_functions

    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )


def get_collection(chroma_dir: Path = CHROMA_DIR, reset: bool = False):
    import chromadb

    chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_dir))
    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass  # first run: nothing to delete
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_embedding_function(),
        # Cosine, not the L2 default: bge embeddings are meant to be compared
        # by angle, and L2 would make longer cards systematically distant.
        metadata={"hnsw:space": "cosine"},
    )


def _metadata_for(card: CreativeCard, representation: str) -> dict:
    metadata = {"creative_id": card.creative_id, "representation": representation}
    for field in METADATA_FIELDS:
        value = getattr(card, field, None)
        if value is not None:
            metadata[field] = value
    return metadata


def build_index(
    cards: list[CreativeCard], chroma_dir: Path = CHROMA_DIR, reset: bool = True
) -> int:
    """Embed every card, plus every analyst summary that exists.

    Returns the number of documents written (>= number of creatives).
    """
    collection = get_collection(chroma_dir, reset=reset)
    ids, documents, metadatas = [], [], []

    for card in cards:
        if card.card_text:
            ids.append(document_id(card.creative_id, CARD))
            documents.append(card.card_text)
            metadatas.append(_metadata_for(card, CARD))
        if card.analyst_summary:
            ids.append(document_id(card.creative_id, SUMMARY))
            documents.append(card.analyst_summary)
            metadatas.append(_metadata_for(card, SUMMARY))

    if ids:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)


def _where_clause(filters: dict | None) -> dict | None:
    """Translate filters to Chroma's `where` syntax.

    Chroma requires an explicit `$and` for multiple conditions; a bare
    multi-key dict is silently interpreted differently across versions.
    """
    if not filters:
        return None
    usable = {k: v for k, v in filters.items() if k in METADATA_FIELDS}
    if not usable:
        return None
    if len(usable) == 1:
        return usable
    return {"$and": [{k: v} for k, v in usable.items()]}


def semantic_search(
    query: str,
    limit: int = 5,
    filters: dict | None = None,
    chroma_dir: Path = CHROMA_DIR,
) -> list[IndexedHit]:
    """Vector search over both representations. Returns raw, undeduped hits.

    Over-fetches (3x) because both representations of one creative may hit,
    and the caller dedupes to creative level afterwards — without the
    over-fetch, a top-5 could collapse to two distinct creatives.
    """
    collection = get_collection(chroma_dir, reset=False)
    if collection.count() == 0:
        return []
    result = collection.query(
        query_texts=[query],
        n_results=min(limit * 3, collection.count()),
        where=_where_clause(filters),
    )
    hits = []
    for doc_id, distance in zip(result["ids"][0], result["distances"][0]):
        creative_id, representation = parse_document_id(doc_id)
        # Chroma returns cosine *distance*; convert so higher is better.
        hits.append(IndexedHit(creative_id, representation, 1.0 - float(distance)))
    return hits


def main() -> None:
    from creativesignal.retrieval.cards import build_all_cards

    cards = build_all_cards()
    with_summary = sum(1 for c in cards if c.analyst_summary)
    n = build_index(cards)
    print(f"indexed {n} documents from {len(cards)} creatives -> {CHROMA_DIR}")
    print(f"  cards: {len(cards)}  analyst summaries: {with_summary}")
    if with_summary == 0:
        print(
            "  No analyst summaries — index is card-only. Run "
            "`python -m creativesignal.retrieval.cards` with an API key (W2.3)."
        )


if __name__ == "__main__":
    main()
