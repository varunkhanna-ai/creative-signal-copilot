"""W5.3: validate the server as a real MCP client over stdio."""
import asyncio, json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command="python", args=["mcp_server/server.py"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("TOOLS:", [t.name for t in tools.tools])

            r = await session.call_tool("search_creatives", {"query": "gentle cleanser", "limit": 2})
            d = json.loads(r.content[0].text)
            print("search hits:", [h["creative_id"] for h in d["hits"]])

            r = await session.call_tool("get_category_stats", {})
            d = json.loads(r.content[0].text)
            print("stats total:", d["total_creatives"], "by_tier:", d["by_tier"])

            cid = "t2_smangrul_0951"
            r = await session.call_tool("get_creative_details", {"creative_id": cid})
            d = json.loads(r.content[0].text)
            print("details found:", d["found"], "->", d.get("creative", {}).get("headline"))

            r = await session.call_tool("generate_evidence_report", {"query": "cleanser", "limit": 3})
            d = json.loads(r.content[0].text)
            print("evidence ids:", d["retrieved_creative_ids"])
            print("coverage:", d["coverage_statement"])
            print("honesty rule present:", "hypothesis" in d["honesty_rule"])

asyncio.run(main())
