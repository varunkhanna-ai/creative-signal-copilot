"""§6: the `CreativeSource` interface every corpus connector conforms to.

The point of the abstraction is the governance story, not polymorphism for
its own sake: a curated local corpus and a hypothetical live ad-library API
should be interchangeable at the call site, so that "we could add a live
source without redesigning retrieval" is demonstrable rather than asserted.

Only `CuratedCorpusConnector` is on the critical path. The live connectors
stay `NotImplementedError` by design (`live_stubs.py`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from creativesignal.schema import Creative


@dataclass(frozen=True)
class SearchFilters:
    """Structured filters a source may apply. All optional; None means "any"."""

    source_type: str | None = None
    category: str | None = None
    platform: str | None = None
    advertiser: str | None = None
    proxy_bucket: str | None = None
    hook_type: str | None = None
    tone: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Non-null filters only — what a query layer actually applies."""
        base = {
            "source_type": self.source_type,
            "category": self.category,
            "platform": self.platform,
            "advertiser": self.advertiser,
            "proxy_bucket": self.proxy_bucket,
            "hook_type": self.hook_type,
            "tone": self.tone,
        }
        return {k: v for k, v in {**base, **self.extra}.items() if v is not None}


@dataclass
class SearchResult:
    """A retrieved creative plus why it was retrieved.

    `score` and `retrieved_by` exist so a result can always explain itself —
    the UI shows provenance, and the eval harness needs to know which
    representation matched (W2.7).
    """

    creative: Creative
    score: float
    retrieved_by: str = "unknown"

    @property
    def creative_id(self) -> str:
        return self.creative.creative_id


class CreativeSource(ABC):
    """A searchable source of creative records."""

    name: str = "base"

    @abstractmethod
    def search(
        self, query: str, filters: SearchFilters | None = None, limit: int = 5
    ) -> list[SearchResult]:
        """Return up to `limit` results, best first."""

    @abstractmethod
    def get(self, creative_id: str) -> Creative | None:
        """Fetch one record by id, or None."""

    @abstractmethod
    def all_creatives(self, filters: SearchFilters | None = None) -> list[Creative]:
        """Every record matching `filters` — used to build indexes and stats."""
