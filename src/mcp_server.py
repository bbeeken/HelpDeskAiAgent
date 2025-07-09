from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Awaitable, Callable, Dict, List



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


class MCPServer:
    """Container for available tools."""

    def __init__(self, tools: List[Tool]) -> None:
        self.tools = tools


def create_server() -> MCPServer:

    """Return a server instance exposing available tools."""

    # Import inside the function to avoid circular imports during module
    # initialization.
    from .tool_list import TOOLS

    # ``list()`` creates a shallow copy so callers cannot mutate the original
    # list defined in :mod:`src.tool_list`.
    return MCPServer(list(TOOLS))

