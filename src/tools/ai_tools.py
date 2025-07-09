"""AI helper tools."""

from __future__ import annotations

from typing import Dict

from ..mcp_server import Tool


async def ai_echo(text: str) -> Dict[str, str]:
    """Echo the provided text. Stand-in for an AI generated response."""
    return {"content": text}


AI_ECHO = Tool(
    name="ai_echo",
    description="Echo text using the AI system.",
    inputSchema={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
    _implementation=ai_echo,
)

__all__ = ["AI_ECHO"]
