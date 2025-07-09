"""AI helper tools."""

from __future__ import annotations

from typing import Dict

from ..enhanced_mcp_server import Tool


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
    category="ai",
    requires_auth=False,
    rate_limit=None,
    _implementation=ai_echo,
)

__all__ = ["AI_ECHO"]
