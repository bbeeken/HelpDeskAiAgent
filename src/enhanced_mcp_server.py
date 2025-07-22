from __future__ import annotations


from typing import Any, Awaitable, Callable, Dict, Iterable, List

import json
import anyio
from mcp.server.stdio import stdio_server

from mcp.server import Server
from mcp import types

from db.mssql import SessionLocal
from .mcp_server import Tool

# Business logic modules
from tools import (
    ai_tools,
    analysis_tools,
    asset_tools,
    attachment_tools,
    category_tools,
    message_tools,
    oncall_tools,
    site_tools,
    status_tools,
    ticket_tools,
    user_tools,
    vendor_tools,
)


async def _with_session(func: Callable[..., Awaitable[Any]], **kwargs: Any) -> Any:
    async with SessionLocal() as db:
        return await func(db, **kwargs)


def _db_wrapper(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    async def wrapper(**kwargs: Any) -> Any:
        return await _with_session(func, **kwargs)

    return wrapper


ENHANCED_TOOLS: List[Tool] = [
    Tool(
        name="get_asset",
        description="Retrieve an asset by ID",
        inputSchema={"type": "object", "properties": {"asset_id": {"type": "integer"}}, "required": ["asset_id"]},
        _implementation=_db_wrapper(asset_tools.get_asset),
    ),
    Tool(
        name="list_assets",
        description="List assets",
        inputSchema={"type": "object", "properties": {"skip": {"type": "integer"}, "limit": {"type": "integer"}}, "required": []},
        _implementation=_db_wrapper(asset_tools.list_assets),
    ),
    Tool(
        name="get_vendor",
        description="Retrieve a vendor by ID",
        inputSchema={"type": "object", "properties": {"vendor_id": {"type": "integer"}}, "required": ["vendor_id"]},
        _implementation=_db_wrapper(vendor_tools.get_vendor),
    ),
    Tool(
        name="list_vendors",
        description="List vendors",
        inputSchema={"type": "object", "properties": {"skip": {"type": "integer"}, "limit": {"type": "integer"}}, "required": []},
        _implementation=_db_wrapper(vendor_tools.list_vendors),
    ),
    Tool(
        name="get_site",
        description="Retrieve a site by ID",
        inputSchema={"type": "object", "properties": {"site_id": {"type": "integer"}}, "required": ["site_id"]},
        _implementation=_db_wrapper(site_tools.get_site),
    ),
    Tool(
        name="list_sites",
        description="List sites",
        inputSchema={"type": "object", "properties": {"skip": {"type": "integer"}, "limit": {"type": "integer"}}, "required": []},
        _implementation=_db_wrapper(site_tools.list_sites),
    ),
    Tool(
        name="list_categories",
        description="List ticket categories",
        inputSchema={"type": "object", "properties": {}, "required": []},
        _implementation=_db_wrapper(category_tools.list_categories),
    ),
    Tool(
        name="list_statuses",
        description="List ticket statuses",
        inputSchema={"type": "object", "properties": {}, "required": []},
        _implementation=_db_wrapper(status_tools.list_statuses),
    ),
    Tool(
        name="get_ticket",
        description="Get expanded ticket by ID",
        inputSchema={"type": "object", "properties": {"ticket_id": {"type": "integer"}}, "required": ["ticket_id"]},
        _implementation=_db_wrapper(ticket_tools.get_ticket_expanded),
    ),
    Tool(
        name="list_tickets",
        description="List expanded tickets",
        inputSchema={
            "type": "object",
            "properties": {
                "skip": {"type": "integer"},
                "limit": {"type": "integer"},
            },
            "required": [],
        },
        _implementation=_db_wrapper(ticket_tools.list_tickets_expanded),
    ),
    Tool(
        name="search_tickets",
        description="Search tickets",
        inputSchema={"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]},
        _implementation=_db_wrapper(ticket_tools.search_tickets_expanded),
    ),
    Tool(
        name="create_ticket",
        description="Create a ticket",
        inputSchema={"type": "object", "properties": {"ticket_obj": {"type": "object"}}, "required": ["ticket_obj"]},
        _implementation=_db_wrapper(ticket_tools.create_ticket),
    ),
    Tool(
        name="update_ticket",
        description="Update a ticket",
        inputSchema={"type": "object", "properties": {"ticket_id": {"type": "integer"}, "updates": {"type": "object"}}, "required": ["ticket_id", "updates"]},
        _implementation=_db_wrapper(ticket_tools.update_ticket),
    ),
    Tool(
        name="delete_ticket",
        description="Delete a ticket",
        inputSchema={"type": "object", "properties": {"ticket_id": {"type": "integer"}}, "required": ["ticket_id"]},
        _implementation=_db_wrapper(ticket_tools.delete_ticket),
    ),
    Tool(
        name="get_ticket_messages",
        description="List messages for a ticket",
        inputSchema={"type": "object", "properties": {"ticket_id": {"type": "integer"}}, "required": ["ticket_id"]},
        _implementation=_db_wrapper(message_tools.get_ticket_messages),
    ),
    Tool(
        name="post_ticket_message",
        description="Post a new ticket message",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer"},
                "message": {"type": "string"},
                "sender_code": {"type": "string"},
                "sender_name": {"type": "string"},
            },
            "required": ["ticket_id", "message", "sender_code", "sender_name"],
        },
        _implementation=_db_wrapper(message_tools.post_ticket_message),
    ),
    Tool(
        name="ticket_attachments",
        description="Get attachments for a ticket",
        inputSchema={"type": "object", "properties": {"ticket_id": {"type": "integer"}}, "required": ["ticket_id"]},
        _implementation=_db_wrapper(attachment_tools.get_ticket_attachments),
    ),
    Tool(
        name="tickets_by_status",
        description="Count tickets by status",
        inputSchema={"type": "object", "properties": {}, "required": []},
        _implementation=_db_wrapper(analysis_tools.tickets_by_status),
    ),
    Tool(
        name="open_tickets_by_site",
        description="Open ticket counts by site",
        inputSchema={"type": "object", "properties": {}, "required": []},
        _implementation=_db_wrapper(analysis_tools.open_tickets_by_site),
    ),
    Tool(
        name="open_tickets_by_user",
        description="Open ticket counts by user",
        inputSchema={"type": "object", "properties": {}, "required": []},
        _implementation=_db_wrapper(analysis_tools.open_tickets_by_user),
    ),
    Tool(
        name="tickets_waiting_user",
        description="Tickets waiting on user",
        inputSchema={"type": "object", "properties": {}, "required": []},
        _implementation=_db_wrapper(analysis_tools.tickets_waiting_on_user),
    ),
    Tool(
        name="sla_breaches",
        description="List ticket IDs breaching SLA and return their count",
        inputSchema={
            "type": "object",
            "properties": {
                "sla_days": {"type": "integer"},
            },
            "required": [],
        },
        _implementation=_db_wrapper(analysis_tools.sla_breaches),
    ),
    Tool(
        name="ticket_trend",
        description="Ticket trend",
        inputSchema={"type": "object", "properties": {"days": {"type": "integer"}}, "required": []},
        _implementation=_db_wrapper(analysis_tools.ticket_trend),
    ),
    Tool(
        name="get_current_oncall",
        description="Get current on-call shift",
        inputSchema={"type": "object", "properties": {}, "required": []},
        _implementation=_db_wrapper(oncall_tools.get_current_oncall),
    ),
    Tool(
        name="list_oncall_schedule",
        description="List on-call schedule",
        inputSchema={"type": "object", "properties": {"skip": {"type": "integer"}, "limit": {"type": "integer"}}, "required": []},
        _implementation=_db_wrapper(oncall_tools.list_oncall_schedule),
    ),
    Tool(
        name="ai_suggest_response",
        description="AI suggested ticket response",
        inputSchema={"type": "object", "properties": {"ticket": {"type": "object"}}, "required": ["ticket"]},
        _implementation=ai_tools.ai_suggest_response,
    ),
    Tool(
        name="get_user_by_email",
        description="Look up user information by email",
        inputSchema={"type": "object", "properties": {"email": {"type": "string"}}, "required": ["email"]},
        _implementation=user_tools.get_user_by_email,
    ),
]
# Keep track of how many tools are defined for easier maintenance.
TOOL_COUNT: int = len(ENHANCED_TOOLS)


def create_server() -> Server:
    server = Server("helpdesk-ai-agent")

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return [
            types.Tool(name=t.name, description=t.description, inputSchema=t.inputSchema)
            for t in ENHANCED_TOOLS

        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: Dict[str, Any]) -> Iterable[types.Content]:

        for tool in ENHANCED_TOOLS:
            if tool.name == name:
                result = await tool._implementation(**arguments)
                text = json.dumps(result)
                return [types.TextContent(type="text", text=text)]
        raise ValueError(f"Unknown tool: {name}")

    server._tools = ENHANCED_TOOLS
    return server


def run_server() -> None:
    """Run the MCP server using stdio transport."""

    async def _main() -> None:
        server = create_server()
        async with stdio_server() as (read, write):
            await server.run(read, write)

    anyio.run(_main)

