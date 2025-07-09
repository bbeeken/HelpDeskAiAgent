"""List of all available tools used by :func:`create_server`."""

from __future__ import annotations

from typing import List

from .mcp_server import Tool, create_enhanced_server

try:
    _server = create_enhanced_server()
    TOOLS: List[Tool] = list(getattr(_server, "_tools", []))
    if not TOOLS:
        raise RuntimeError("no enhanced tools")
except Exception:
    from .tools import GET_TICKET, TICKET_COUNT, AI_ECHO

    TOOLS = [GET_TICKET, TICKET_COUNT, AI_ECHO]
