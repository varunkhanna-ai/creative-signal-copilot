# MCP validation transcript (W5.3)

`creative-intelligence-mcp` validated as a real MCP client over **stdio JSON-RPC** —
not by calling the Python functions directly, which would prove nothing about the
protocol layer.

Client script: `tests/test_mcp_client.py` (also runnable standalone).

## Session

```
TOOLS: ['search_creatives', 'get_creative_details', 'get_category_stats', 'generate_evidence_report']

> search_creatives(query="gentle cleanser", limit=2)
  hits: ['t2_smangrul_0951', 't2_jaykin_0383']

> get_category_stats()
  total_creatives: 9
  by_tier: {'tier2': 9}

> get_creative_details(creative_id="t2_smangrul_0951")
  found: True -> "Facial Cleanser"

> generate_evidence_report(query="cleanser", limit=3)
  retrieved_creative_ids: ['t2_smangrul_0951', 't2_jaykin_0383', 't2_smangrul_0595']
  coverage_statement: "Based on 3 retrieved examples; descriptive, not causal."
  honesty_rule: present
```

## What this demonstrates

- All four tools are discoverable and callable over stdio.
- Every payload carries the honesty rule and, where applicable, a coverage statement —
  the framing survives leaving our UI, which is the whole point of putting it in the
  payload rather than in a footer.
- The server runs with **no `ANTHROPIC_API_KEY`**: every tool is retrieval and
  arithmetic. `generate_evidence_report` deliberately makes no LLM call, so calling it
  from someone else's coding agent cannot spend tokens.
- `by_tier: {'tier2': 9}` is the corpus gap (decision-log B1/B2) visible through the
  MCP surface — the server reports the corpus it actually has.

## Registering the server

**Claude Code** (W5.5) — `.mcp.json` at the repo root:

```json
{
  "mcpServers": {
    "creative-intelligence": {
      "command": "python",
      "args": ["mcp_server/server.py"]
    }
  }
}
```

**Kilo Code** (W5.2/W5.3 routing) — same command/args in its MCP settings panel.

Both clients hit the same corpus and the same tool layer the Streamlit app uses,
which is the interoperability claim this week exists to demonstrate.
