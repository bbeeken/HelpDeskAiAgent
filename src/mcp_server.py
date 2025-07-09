from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional
import logging
import os

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
    category: str = ""
    requires_auth: bool = False
    rate_limit: Optional[str] = None

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

    server._tools = TOOLS
    server.is_enhanced = False
    return server


def run_server() -> None:
    """Run the MCP server using stdio transport."""

    async def _main() -> None:
        server = create_server()
        async with stdio_server() as (read, write):
            await server.run(read, write)

    anyio.run(_main)


def create_enhanced_server() -> Server:
    """Attempt to create the enhanced server. Fallback to :func:`create_server`."""

    env = os.getenv("ENABLE_ENHANCED_MCP", "1").lower()
    if env in {"0", "false", "no"}:
        logging.info("Enhanced MCP disabled via environment")
        return create_server()

    try:
        from .enhanced_mcp_server import ENHANCED_TOOLS, create_server as _create
        from .tool_list import TOOLS
        TOOLS.clear()
        TOOLS.extend(ENHANCED_TOOLS)
        server = _create()
        server.is_enhanced = True
        server._tools = TOOLS
        logging.info(
            "Enhanced MCP server loaded with %d tools", len(server._tools)
        )
        return server
    except Exception as exc:  # pragma: no cover - unexpected
        logging.exception("Failed to load enhanced server: %s", exc)
        base = create_server()
        base.is_enhanced = False
        return base

