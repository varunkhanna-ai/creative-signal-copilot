"""Interface-conforming stubs for live ad platforms. These never work.

They exist to prove the `CreativeSource` interface generalizes beyond the
curated corpus — and to make the governance boundary legible in code: this
project does not scrape and does not call Meta/TikTok APIs (AGENTS.md).

Every method raises `NotImplementedError` with the reason. Do not implement
them; that is a deliberate project constraint, not an unfinished task.
"""

from __future__ import annotations

from creativesignal.schema import Creative
from creativesignal.sources.base import CreativeSource, SearchFilters, SearchResult

_REASON = (
    "{name} is an interface stub and is never implemented. CreativeSignal "
    "uses the curated local corpus only — no scrapers, no live platform API "
    "calls. See AGENTS.md and docs/data-governance.md."
)


class _LiveConnector(CreativeSource):
    """Shared refusal behavior for every live-platform stub."""

    name = "live"

    def _refuse(self):
        raise NotImplementedError(_REASON.format(name=type(self).__name__))

    def search(
        self, query: str, filters: SearchFilters | None = None, limit: int = 5
    ) -> list[SearchResult]:
        self._refuse()

    def get(self, creative_id: str) -> Creative | None:
        self._refuse()

    def all_creatives(self, filters: SearchFilters | None = None) -> list[Creative]:
        self._refuse()


class MetaLiveConnector(_LiveConnector):
    """Would wrap the Meta Ad Library API. Deliberately unimplemented."""

    name = "meta_live"


class TikTokConnector(_LiveConnector):
    """Would wrap the TikTok Creative Center. Deliberately unimplemented."""

    name = "tiktok_live"
