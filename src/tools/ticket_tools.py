"""Minimal ticket management tools used for demonstration."""

from __future__ import annotations

from typing import Any, Dict

from ..mcp_server import Tool


async def get_ticket(ticket_id: int) -> Dict[str, Any]:
    """Return details for a ticket."""
    return {"ticket_id": ticket_id}


GET_TICKET = Tool(
    name="get_ticket",
    description="Return details for a ticket by id.",
    inputSchema={
        "type": "object",
        "properties": {"ticket_id": {"type": "integer"}},
        "required": ["ticket_id"],
    },
    _implementation=get_ticket,
)

__all__ = ["GET_TICKET"]
