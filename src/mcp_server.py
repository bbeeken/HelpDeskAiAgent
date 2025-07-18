from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Iterable, List
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
import anyio
import json



@dataclass
class Tool:
    """Simple representation of a callable tool."""

    name: str
    description: str
    inputSchema: Dict[str, Any]
    _implementation: Callable[..., Awaitable[Any]]

    category: str | None = None
    requires_auth: bool = False
    rate_limit: str | None = None


    def to_dict(self) -> Dict[str, Any]:
        # Serialize public fields while omitting the implementation callable
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.inputSchema,
            "category": self.category,
            "requires_auth": self.requires_auth,
            "rate_limit": self.rate_limit,
        }


def create_enhanced_server() -> Server:
    """Create the enhanced MCP server with full tool set."""

    from .enhanced_mcp_server import ENHANCED_TOOLS, create_server as _create

    server = _create()
    server.is_enhanced = True
    server._tools = ENHANCED_TOOLS
    logging.info("Enhanced MCP server loaded with %d tools", len(server._tools))
    return server


def create_server() -> Server:
    """Compatibility wrapper for :func:`create_enhanced_server`."""

    return create_enhanced_server()


def run_server() -> None:
    """Run the MCP server using stdio transport."""

    async def _main() -> None:
        server = create_enhanced_server()
        async with stdio_server() as (read, write):
            await server.run(read, write)

    anyio.run(_main)

