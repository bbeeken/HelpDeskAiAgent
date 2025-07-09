"""Analytics related tools."""

from __future__ import annotations

from typing import Dict

from ..enhanced_mcp_server import Tool


async def ticket_count() -> Dict[str, int]:
    """Return the number of tickets (dummy implementation)."""
    # In a real implementation this would query a database.
    return {"count": 0}


TICKET_COUNT = Tool(
    name="ticket_count",
    description="Return the total number of tickets.",
    inputSchema={"type": "object", "properties": {}, "required": []},
    category="analytics",
    requires_auth=False,
    rate_limit=None,
    _implementation=ticket_count,
)

__all__ = ["TICKET_COUNT"]
