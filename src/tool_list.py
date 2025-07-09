"""List of all available tools used by :func:`create_server`."""

from __future__ import annotations

from typing import List

from .enhanced_mcp_server import Tool
from .tools import GET_TICKET, TICKET_COUNT, AI_ECHO

TOOLS: List[Tool] = [
    GET_TICKET,
    TICKET_COUNT,
    AI_ECHO,
]
