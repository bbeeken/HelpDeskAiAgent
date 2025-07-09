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

    async def get_ticket(ticket_id: int) -> Dict[str, Any]:
        """Return a simple representation of a ticket."""
        return {"ticket_id": ticket_id}

    async def create_ticket(subject: str, body: str) -> Dict[str, Any]:
        """Pretend to create a ticket and return its info."""
        return {"ticket_id": 1, "subject": subject, "ticket_body": body}

    tools = [
        Tool(
            name="get_ticket",
            description="Fetch a ticket by ID.",
            inputSchema={
                "type": "object",
                "properties": {"ticket_id": {"type": "integer"}},
                "required": ["ticket_id"],
            },
            _implementation=get_ticket,
        ),
        Tool(
            name="create_ticket",
            description="Create a new ticket.",
            inputSchema={
                "type": "object",
                "properties": {
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["subject", "body"],
            },
            _implementation=create_ticket,
        ),
    ]

    return MCPServer(tools)
