import logging
import os
from typing import Any, Dict

from fastmcp import Client

MCP_URL = os.getenv("MCP_URL", "http://localhost:8080")

logger = logging.getLogger(__name__)

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(MCP_URL)
    return _client


async def suggest_ticket_response(ticket: Dict[str, Any], context: str = "") -> str:
    client = _get_client()
    async with client:
        try:
            result = await client.call_tool(
                "suggest_ticket_response",
                {"ticket": ticket, "context": context},
            )
            if result.data is not None:
                return str(result.data)
            if result.content:
                from fastmcp.utilities.types import TextContent
                for block in result.content:
                    if isinstance(block, TextContent):
                        return block.text
        except Exception:
            logger.exception("FastMCP request failed")
    return ""
