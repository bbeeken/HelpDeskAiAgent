"""List of available tools for the MCP server."""

from __future__ import annotations

from typing import List


from .mcp_server import Tool
from .enhanced_mcp_server import ENHANCED_TOOLS

# Alias used by the HTTP server and tests
TOOLS: List[Tool] = ENHANCED_TOOLS

