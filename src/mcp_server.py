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
    """Return a server instance exposing demo tools."""

    async def echo(text: str) -> Dict[str, Any]:
        return {"echo": text}

    async def add(a: int, b: int) -> Dict[str, Any]:
        return {"result": a + b}

    tools = [
        Tool(
            name="echo",
            description="Return the provided text.",
            inputSchema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            _implementation=echo,
        ),
        Tool(
            name="add",
            description="Add two integers.",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
                "required": ["a", "b"],
            },
            _implementation=add,
        ),
    ]

    return MCPServer(tools)
