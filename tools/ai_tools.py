"""Helper functions for interacting with the AI backend."""

from typing import Any, AsyncGenerator, Dict
import logging
from datetime import datetime, UTC

from pydantic import ValidationError
from schemas.ticket import TicketOut

from ai.mcp_agent import (
    suggest_ticket_response as mcp_suggest_response,
    stream_ticket_response as mcp_stream_ticket_response,
)

logger = logging.getLogger(__name__)


async def ai_suggest_response(ticket: Dict[str, Any], context: str = "") -> Dict[str, Any]:
    """Return a suggested response using the MCP backend.

    Parameters
    ----------
    ticket: dict
        Ticket information validated against :class:`schemas.ticket.TicketOut`.
    context: str, optional
        Additional conversation context for the AI model.

    Returns
    -------
    dict
        Dictionary containing ``content`` with the generated text,
        ``model_used`` describing the backend and ``generated_at`` with the
        timestamp.
    """

    try:
        TicketOut.model_validate(ticket)
    except ValidationError as exc:
        logger.error("Invalid ticket provided to ai_suggest_response: %s", exc)
        raise

    try:
        content = await mcp_suggest_response(ticket, context)
    except Exception as exc:  # pragma: no cover - network/agent errors
        logger.exception("mcp_agent request failed: %s", exc)
        content = ""

    return {
        "content": content,
        "model_used": "mcp_agent",
        "generated_at": datetime.now(UTC).isoformat(),
    }


async def ai_stream_response(
    ticket: Dict[str, Any], context: str = ""
) -> AsyncGenerator[Dict[str, Any], None]:
    """Stream a suggested response to the ticket.

    Parameters
    ----------
    ticket: dict
        Ticket information validated against :class:`schemas.ticket.TicketOut`.
    context: str, optional
        Additional conversation context for the AI model.

    Yields
    ------
    dict
        Dictionaries with the same structure as :func:`ai_suggest_response`.
    """

    try:
        TicketOut.model_validate(ticket)
    except ValidationError as exc:
        logger.error("Invalid ticket provided to ai_stream_response: %s", exc)
        return

    try:
        async for chunk in mcp_stream_ticket_response(ticket, context):
            yield {
                "content": chunk,
                "model_used": "mcp_agent",
                "generated_at": datetime.now(UTC).isoformat(),
            }
    except Exception as exc:  # pragma: no cover - network/agent errors
        logger.exception("mcp_agent streaming request failed: %s", exc)
