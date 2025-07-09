from __future__ import annotations

"""MCP server implementation with optional enhanced features."""

from dataclasses import dataclass, asdict
from typing import Any, Awaitable, Callable, Dict, Iterable

import anyio
import json
import logging
import os

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

# Environment flags for optional functionality
ENABLE_RATE_LIMITING = os.getenv("ENABLE_RATE_LIMITING", "true").lower() == "true"
ERROR_TRACKING_DSN = os.getenv("ERROR_TRACKING_DSN")

logger = logging.getLogger(__name__)

if ERROR_TRACKING_DSN:
    logger.info("Error tracking enabled")


@dataclass
class Tool:
    """Simple representation of a callable tool."""

    name: str
    description: str
    inputSchema: Dict[str, Any]
    _implementation: Callable[..., Awaitable[Any]]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("_implementation", None)
        return data


def create_server() -> Server:
    """Return a server instance exposing available tools."""

    server = Server("helpdesk-ai-agent")

    # Import inside function to avoid circular imports.
    from .tool_list import TOOLS

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=t.name,
                description=t.description,
                inputSchema=t.inputSchema,
            )
            for t in TOOLS
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: Dict[str, Any]) -> Iterable[types.Content]:
        for tool in TOOLS:
            if tool.name == name:
                result = await tool._implementation(**arguments)
                text = json.dumps(result)
                return [types.TextContent(type="text", text=text)]
        raise ValueError(f"Unknown tool: {name}")

    return server


def run_server() -> None:
    """Run the MCP server using stdio transport."""

    async def _main() -> None:
        server = create_server()
        async with stdio_server() as (read, write):
            await server.run(read, write)

    anyio.run(_main)
