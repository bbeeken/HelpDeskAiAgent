from typing import Any, Dict
import os
import logging

from ai.mcp_agent import suggest_ticket_response as mcp_suggest_response

logger = logging.getLogger(__name__)


async def ai_suggest_response(ticket: Dict[str, Any], context: str = "") -> str:
    if os.getenv("OPENAI_API_KEY"):
        from ai.openai_agent import suggest_ticket_response as openai_suggest_response
        return await openai_suggest_response(ticket, context)
    return await mcp_suggest_response(ticket, context)
