import logging
import os
from typing import Any, AsyncGenerator, Dict

from fastmcp import Client

MCP_URL = os.getenv("MCP_URL", "http://localhost:8080")
MCP_STREAM_TIMEOUT = int(os.getenv("MCP_STREAM_TIMEOUT", "30"))

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


async def stream_ticket_response(
    ticket: Dict[str, Any], context: str = ""
) -> AsyncGenerator[str, None]:
    """Yield a suggested ticket response using FastMCP's streaming API."""
    client = _get_client()
    async with client:
        if hasattr(client, "stream_tool"):
            try:
                async for chunk in client.stream_tool(
                    "suggest_ticket_response",
                    {"ticket": ticket, "context": context},
                    timeout=MCP_STREAM_TIMEOUT,
                ):
                    if getattr(chunk, "data", None) is not None:
                        yield str(chunk.data)
                    elif getattr(chunk, "content", None):
                        from fastmcp.utilities.types import TextContent

                        for block in chunk.content:
                            if isinstance(block, TextContent):
                                yield block.text
            except Exception:
                logger.exception("FastMCP streaming request failed")
        else:
            # Library version without stream_tool - fall back to single call
            result = await suggest_ticket_response(ticket, context)
            if result:
                yield result
