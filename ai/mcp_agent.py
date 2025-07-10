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
_connection_failures = 0
_max_failures = 3
_circuit_open = False


async def _get_client() -> "ClientSessionGroup | None":
    """Return a connected MCP client instance with circuit breaker."""

    global _client, _connection_failures, _circuit_open

    if _circuit_open:
        logger.warning("MCP circuit breaker is open, skipping connection")
        return None

    if ClientSessionGroup is None:
        raise ImportError("mcp package is required for MCP operations")

    if _client is None or not getattr(_client, "sessions", []):
        try:
            _client = ClientSessionGroup()
            await asyncio.wait_for(
                _client.connect_to_server(StreamableHttpParameters(url=MCP_URL)),
                timeout=MCP_STREAM_TIMEOUT,
            )
            _connection_failures = 0
        except (asyncio.TimeoutError, Exception) as e:
            logger.error("MCP connection failed: %s", e)
            _connection_failures += 1
            if _connection_failures >= _max_failures:
                _circuit_open = True
                logger.error("MCP circuit breaker opened")
            return None
    return _client


async def suggest_ticket_response(ticket: Dict[str, Any], context: str = "") -> str:
    client = await _get_client()
    if not client:
        return ""
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

    async def _generator() -> AsyncGenerator[str, None]:
        if not client:
            if False:
                yield ""
            return

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

    return _generator()
