import logging
import os
import asyncio
from typing import Any, AsyncGenerator, Dict

try:
    from mcp.client.session_group import (
        ClientSessionGroup,
        StreamableHttpParameters,
    )
    from mcp.types import TextContent
except Exception:  # pragma: no cover - optional dependency
    ClientSessionGroup = None  # type: ignore
    StreamableHttpParameters = None  # type: ignore
    TextContent = None  # type: ignore

MCP_URL = os.getenv("MCP_URL", "http://localhost:8008")
MCP_STREAM_TIMEOUT = int(os.getenv("MCP_STREAM_TIMEOUT", "30"))

logger = logging.getLogger(__name__)

_client: ClientSessionGroup | None = None


async def _get_client() -> "ClientSessionGroup":
    """Return a connected MCP client instance.

    The global client may be closed after use in a context manager. This
    helper recreates and reconnects the client if no active sessions are
    present so callers always get a usable connection.
    """

    if ClientSessionGroup is None:
        raise ImportError("mcp package is required for MCP operations")

    global _client
    if _client is None or not getattr(_client, "sessions", []):
        _client = ClientSessionGroup()
        await _client.connect_to_server(
            StreamableHttpParameters(url=MCP_URL)
        )
    return _client


async def suggest_ticket_response(ticket: Dict[str, Any], context: str = "") -> str:
    client = await _get_client()
    async with client:
        try:
            result = await client.call_tool(
                "suggest_ticket_response",
                {"ticket": ticket, "context": context},
            )
            if result.content:
                for block in result.content:
                    if isinstance(block, TextContent):
                        return block.text
        except Exception:
            logger.exception("MCP request failed")
    return ""


async def stream_ticket_response(
    ticket: Dict[str, Any], context: str = ""
) -> AsyncGenerator[str, None]:
    """Yield a suggested ticket response using MCP's progress streaming."""
    client = await _get_client()

    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _progress(progress: float, total: float | None, message: str | None) -> None:
        if message:
            await queue.put(message)

    async def _call() -> None:
        try:
            session = client._tool_to_session["suggest_ticket_response"]
            session_tool_name = client.tools["suggest_ticket_response"].name
            result = await session.call_tool(
                session_tool_name,
                {"ticket": ticket, "context": context},
                progress_callback=_progress,
            )
            # If the server did not stream any chunks, fall back to final content
            if result.content:
                for block in result.content:
                    if isinstance(block, TextContent):
                        await queue.put(block.text)
        except Exception:
            logger.exception("MCP streaming request failed")
        finally:
            await queue.put(None)

    async with client:
        task = asyncio.create_task(_call())
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk
        await task

