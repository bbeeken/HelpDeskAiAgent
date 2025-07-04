from typing import Any, AsyncGenerator, Dict
import os
import logging

from ai.mcp_agent import (
    suggest_ticket_response as mcp_suggest_response,
    stream_ticket_response as mcp_stream_ticket_response,
)

logger = logging.getLogger(__name__)


async def ai_suggest_response(ticket: Dict[str, Any], context: str = "") -> str:
    if os.getenv("OPENAI_API_KEY"):
        from ai.openai_agent import suggest_ticket_response as openai_suggest_response
        return await openai_suggest_response(ticket, context)
    return await mcp_suggest_response(ticket, context)


async def ai_stream_response(
    ticket: Dict[str, Any], context: str = ""
) -> AsyncGenerator[str, None]:
    """Stream a suggested response to the ticket."""
    if os.getenv("OPENAI_API_KEY"):
        # OpenAI helper does not support streaming; fall back to one-shot result
        from ai.openai_agent import suggest_ticket_response as openai_suggest_response
        yield await openai_suggest_response(ticket, context)
        return

    async for chunk in mcp_stream_ticket_response(ticket, context):
        yield chunk
