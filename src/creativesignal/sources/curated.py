"""The curated local corpus — the only `CreativeSource` on the critical path.

Reads `data/corpus.sqlite`. Search here is deliberately naive BM25 over raw
copy (W1.11): the Week-2 hybrid pipeline is meant to be a measurable
improvement over this baseline, so this stays simple on purpose.

No API key is needed anywhere in this module (§7).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from creativesignal.schema import Creative
from creativesignal.sources.base import CreativeSource, SearchFilters, SearchResult

DB_PATH = Path("data/corpus.sqlite")

# Filters that live on `creatives`; hook_type/tone live on `annotations` and
# are joined in only when asked for, keeping the common query a single table.
_CREATIVE_FILTERS = ("source_type", "category", "platform", "advertiser", "proxy_bucket")
_ANNOTATION_FILTERS = ("hook_type", "tone")


def _row_to_creative(row: sqlite3.Row) -> Creative:
    return Creative.model_validate(dict(row))


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens. Shared by indexing and querying.

    Kept trivial and shared — an index/query tokenizer mismatch is the
    classic silent BM25 bug.
    """
    return [t for t in "".join(c if c.isalnum() else " " for c in text.lower()).split() if t]


class CuratedCorpusConnector(CreativeSource):
    name = "curated"

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._bm25 = None
        self._indexed: list[Creative] = []

    # --- storage ---------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"{self.db_path} missing — run `make ingest` first (W1.4)."
            )
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def all_creatives(self, filters: SearchFilters | None = None) -> list[Creative]:
        active = (filters or SearchFilters()).as_dict()
        creative_clauses, params = [], []
        for key in _CREATIVE_FILTERS:
            if key in active:
                creative_clauses.append(f"c.{key} = ?")
                params.append(active[key])

        annotation_clauses = []
        for key in _ANNOTATION_FILTERS:
            if key in active:
                annotation_clauses.append(f"a.{key} = ?")
                params.append(active[key])

        sql = "SELECT DISTINCT c.* FROM creatives c"
        if annotation_clauses:
            sql += " JOIN annotations a ON a.creative_id = c.creative_id"
        clauses = creative_clauses + annotation_clauses
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY c.creative_id"

        with self._connect() as conn:
            return [_row_to_creative(row) for row in conn.execute(sql, params)]

    def get(self, creative_id: str) -> Creative | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM creatives WHERE creative_id = ?", (creative_id,)
            ).fetchone()
        return _row_to_creative(row) if row else None

    # --- naive BM25 search (W1.11) ---------------------------------------

    @staticmethod
    def _document(creative: Creative) -> str:
        return f"{creative.headline or ''} {creative.body_copy or ''}".strip()

    def _ensure_index(self, filters: SearchFilters | None) -> None:
        """Rebuild BM25 over the filtered subset.

        Filters are a hard pre-filter: BM25 scores are corpus-relative, so
        scoring the whole corpus and filtering afterwards would produce
        scores that don't correspond to the returned set.
        """
        from rank_bm25 import BM25Okapi

        self._indexed = [c for c in self.all_creatives(filters) if self._document(c)]
        corpus = [tokenize(self._document(c)) for c in self._indexed]
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def search(
        self, query: str, filters: SearchFilters | None = None, limit: int = 5
    ) -> list[SearchResult]:
        self._ensure_index(filters)
        if self._bm25 is None:
            return []
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(
            zip(self._indexed, scores), key=lambda pair: pair[1], reverse=True
        )
        return [
            SearchResult(creative=creative, score=float(score), retrieved_by="bm25")
            for creative, score in ranked[:limit]
            if score > 0  # a zero score is "no term overlap", not a weak match
        ]
