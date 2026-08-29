"""W5.2/W5.3: MCP tool contracts and the read-only guarantee.

The read-only test is the important one — AGENTS.md forbids writes from the
MCP server, and "we didn't write any write code" is a weaker guarantee than
"the connection physically cannot write."
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_server.server import (  # noqa: E402
    generate_evidence_report,
    get_category_stats,
    get_creative_details,
    readonly_connection,
    search_creatives,
)


def _payload(raw: str) -> dict:
    return json.loads(raw)


# --- read-only guarantee --------------------------------------------------


def test_connection_is_physically_read_only():
    """Enforced at the driver, not by discipline."""
    with readonly_connection() as conn:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute(
                "INSERT INTO creatives (creative_id, source_type, advertiser, "
                "platform, category, date_observed, rights_note) VALUES "
                "('hack', 'tier2', 'x', 'y', 'z', '2026-01-01', 'n')"
            )


def test_readonly_connection_can_still_read():
    with readonly_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM creatives").fetchone()[0] >= 0


def test_server_module_imports_no_write_functions():
    """A structural check: no write symbol is reachable from the server."""
    import mcp_server.server as server

    forbidden = ("save_run", "insert_creatives", "write_annotations", "save_summary")
    for name in forbidden:
        assert not hasattr(server, name), f"{name} must not be importable here"


# --- honesty framing travels with the payload ----------------------------


@pytest.mark.parametrize(
    "raw",
    [
        search_creatives("cleanser", limit=3),
        get_category_stats(),
        generate_evidence_report("cleanser", limit=3),
        get_creative_details("nope"),
    ],
)
def test_every_tool_carries_the_honesty_rule(raw):
    """Outside our UI there is no footer — it must ride in the payload."""
    assert "hypothesis, not a performance claim" in _payload(raw)["honesty_rule"]


# --- search_creatives -----------------------------------------------------


def test_search_returns_cited_hits_with_coverage():
    payload = _payload(search_creatives("gentle cleanser", limit=3))
    assert payload["query"] == "gentle cleanser"
    assert len(payload["hits"]) <= 3
    assert "descriptive, not causal" in payload["coverage_statement"]
    for hit in payload["hits"]:
        assert hit["creative_id"]


def test_search_respects_a_tier_filter():
    payload = _payload(search_creatives("cleanser", source_type="tier3"))
    assert payload["filters_applied"].get("source_type") == "tier3"


def test_off_topic_query_still_returns_nearest_neighbours():
    """Documents real behavior, and the limitation it implies (Entry #20).

    Vector search has no relevance floor — an off-topic query returns the
    corpus's nearest neighbours anyway. The coverage statement travels with
    the payload so a caller can see how thin the basis is.
    """
    payload = _payload(search_creatives("cryptocurrency derivatives", limit=3))
    assert "coverage_statement" in payload
    for hit in payload["hits"]:
        assert hit["creative_id"]


# --- get_creative_details -------------------------------------------------


def test_details_for_unknown_id_returns_a_message_not_an_exception():
    payload = _payload(get_creative_details("does_not_exist"))
    assert payload["found"] is False
    assert "No creative" in payload["message"]


def test_details_returns_the_full_record_for_a_real_id():
    first = _payload(search_creatives("cleanser", limit=1))["hits"]
    if not first:
        pytest.skip("corpus is empty")
    payload = _payload(get_creative_details(first[0]["creative_id"]))
    assert payload["found"] is True
    assert payload["creative"]["creative_id"] == first[0]["creative_id"]


# --- get_category_stats ---------------------------------------------------


def test_category_stats_reports_composition_and_provenance():
    payload = _payload(get_category_stats())
    assert payload["total_creatives"] >= 0
    assert "by_tier" in payload
    assert "/" in payload["provenance_coverage"]
    assert "synthetic" in payload["caveat"]


def test_category_stats_filters_by_category():
    payload = _payload(get_category_stats("skincare"))
    assert payload["category"] == "skincare"


# --- generate_evidence_report --------------------------------------------


def test_evidence_report_makes_no_llm_call(monkeypatch):
    """Must not spend someone else's tokens from their coding agent."""
    import creativesignal.llm as llm

    def _fail(*args, **kwargs):
        raise AssertionError("generate_evidence_report must not call the LLM")

    monkeypatch.setattr(llm, "complete", _fail)
    payload = _payload(generate_evidence_report("cleanser", limit=3))
    assert "retrieved_creative_ids" in payload


def test_evidence_report_carries_coverage_and_caveat():
    payload = _payload(generate_evidence_report("cleanser", limit=3))
    assert "descriptive, not causal" in payload["coverage_statement"]
    assert payload["caveat"]
    assert "not a performance claim" in payload["patterns_note"] or not payload["patterns"]


def test_evidence_report_evidence_blocks_carry_ids():
    payload = _payload(generate_evidence_report("cleanser", limit=3))
    for block in payload["evidence"]:
        assert block["creative_id"]
