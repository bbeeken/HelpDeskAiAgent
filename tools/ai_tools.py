from typing import Any, AsyncGenerator, Dict
import logging

from ai.mcp_agent import (
    suggest_ticket_response as mcp_suggest_response,
    stream_ticket_response as mcp_stream_ticket_response,
)

logger = logging.getLogger(__name__)


async def ai_suggest_response(ticket: Dict[str, Any], context: str = "") -> str:
    """Return a suggested response using the MCP backend."""
    return await mcp_suggest_response(ticket, context)


async def ai_stream_response(
    ticket: Dict[str, Any], context: str = ""
) -> AsyncGenerator[str, None]:
    """Stream a suggested response to the ticket."""
    async for chunk in mcp_stream_ticket_response(ticket, context):
        yield chunk
