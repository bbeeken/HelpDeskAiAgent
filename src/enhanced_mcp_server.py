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


async def _search_tickets_smart(
    db: Any,
    query: str,
    limit: int = 10,
    include_closed: bool = False,
    filters: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Helper to call :meth:`TicketTools.search_tickets_smart`."""
    tools = ticket_tools.TicketTools(db)
    return await tools.search_tickets_smart(
        query=query,
        filters=filters,
        limit=limit,
        include_closed=include_closed,
    )


async def _open_tickets_by_user_tool(db: Any, **kwargs: Any) -> Any:
    """Pass kwargs as filters to open_tickets_by_user."""
    filters = kwargs or None
    return await analysis_tools.open_tickets_by_user(db, filters=filters)


ENHANCED_TOOLS: List[Tool] = [
    Tool(
        name="g_asset",
        description="Retrieve an asset by ID",
        inputSchema={"type": "object", "properties": {"asset_id": {"type": "integer"}}, "required": ["asset_id"]},
        _implementation=_db_wrapper(asset_tools.get_asset),
    ),
    Tool(
        name="l_assets",
        description="List assets",
        inputSchema={"type": "object", "properties": {"skip": {"type": "integer"}, "limit": {"type": "integer"}}, "required": []},
        _implementation=_db_wrapper(asset_tools.list_assets),
    ),
    Tool(
        name="g_vendor",
        description="Retrieve a vendor by ID",
        inputSchema={"type": "object", "properties": {"vendor_id": {"type": "integer"}}, "required": ["vendor_id"]},
        _implementation=_db_wrapper(vendor_tools.get_vendor),
    ),
    Tool(
        name="l_vends",
        description="List vendors",
        inputSchema={"type": "object", "properties": {"skip": {"type": "integer"}, "limit": {"type": "integer"}}, "required": []},
        _implementation=_db_wrapper(vendor_tools.list_vendors),
    ),
    Tool(
        name="g_site",
        description="Retrieve a site by ID",
        inputSchema={"type": "object", "properties": {"site_id": {"type": "integer"}}, "required": ["site_id"]},
        _implementation=_db_wrapper(site_tools.get_site),
    ),
    Tool(
        name="l_sites",
        description="List sites",
        inputSchema={"type": "object", "properties": {"skip": {"type": "integer"}, "limit": {"type": "integer"}}, "required": []},
        _implementation=_db_wrapper(site_tools.list_sites),
    ),
    Tool(
        name="l_cats",
        description="List ticket categories",
        inputSchema={"type": "object", "properties": {}, "required": []},
        _implementation=_db_wrapper(category_tools.list_categories),
    ),
    Tool(
        name="l_status",
        description="List ticket statuses",
        inputSchema={"type": "object", "properties": {}, "required": []},
        _implementation=_db_wrapper(status_tools.list_statuses),
    ),
    Tool(
        name="g_ticket",
        description="Get expanded ticket by ID",
        inputSchema={"type": "object", "properties": {"ticket_id": {"type": "integer"}}, "required": ["ticket_id"]},
        _implementation=_db_wrapper(ticket_tools.get_ticket_expanded),
    ),
    Tool(
        name="l_tkts",
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
        name="s_tkts",
        description="Search tickets",
        inputSchema={"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]},
        _implementation=_db_wrapper(ticket_tools.search_tickets_expanded),
    ),
    Tool(
        name="s_tk_sm",
        description="Search tickets using natural language",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
                "include_closed": {"type": "boolean"},
                "filters": {"type": "object"},
            },
            "required": ["query"],
        },
        _implementation=_db_wrapper(_search_tickets_smart),
    ),
    Tool(
        name="c_ticket",
        description="Create a ticket",
        inputSchema={"type": "object", "properties": {"ticket_obj": {"type": "object"}}, "required": ["ticket_obj"]},
        _implementation=_db_wrapper(ticket_tools.create_ticket),
    ),
    Tool(
        name="u_ticket",
        description="Update a ticket",
        inputSchema={"type": "object", "properties": {"ticket_id": {"type": "integer"}, "updates": {"type": "object"}}, "required": ["ticket_id", "updates"]},
        _implementation=_db_wrapper(ticket_tools.update_ticket),
    ),
    Tool(
        name="d_ticket",
        description="Delete a ticket",
        inputSchema={"type": "object", "properties": {"ticket_id": {"type": "integer"}}, "required": ["ticket_id"]},
        _implementation=_db_wrapper(ticket_tools.delete_ticket),
    ),
    Tool(
        name="g_tmsg",
        description="List messages for a ticket",
        inputSchema={"type": "object", "properties": {"ticket_id": {"type": "integer"}}, "required": ["ticket_id"]},
        _implementation=_db_wrapper(message_tools.get_ticket_messages),
    ),
    Tool(
        name="p_tmsg",
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
        name="t_attach",
        description="Get attachments for a ticket",
        inputSchema={"type": "object", "properties": {"ticket_id": {"type": "integer"}}, "required": ["ticket_id"]},
        _implementation=_db_wrapper(attachment_tools.get_ticket_attachments),
    ),
    Tool(
        name="t_status",
        description="Count tickets by status",
        inputSchema={"type": "object", "properties": {}, "required": []},
        _implementation=_db_wrapper(analysis_tools.tickets_by_status),
    ),
    Tool(
        name="op_site",
        description="Open ticket counts by site",
        inputSchema={"type": "object", "properties": {}, "required": []},
        _implementation=_db_wrapper(analysis_tools.open_tickets_by_site),
    ),
    Tool(
        name="op_user",
        description="Open ticket counts by user",
        inputSchema={
            "type": "object",
            "properties": {
                "Assigned_Email": {"type": "string"},
                "Assigned_Name": {"type": "string"},
            },
            "required": [],
        },
        _implementation=_db_wrapper(_open_tickets_by_user_tool),
    ),
    Tool(
        name="by_user",
        description="List tickets related to a user",
        inputSchema={
            "type": "object",
            "properties": {
                "identifier": {"type": "string"},
                "skip": {"type": "integer"},
                "limit": {"type": "integer"},
            },
            "required": ["identifier"],
        },
        _implementation=_db_wrapper(ticket_tools.get_tickets_by_user),
    ),
    Tool(
        name="staff_rp",
        description="Summary counts of tickets for a technician",
        inputSchema={
            "type": "object",
            "properties": {
                "email": {"type": "string"},
                "start_date": {"type": "string", "format": "date-time"},
                "end_date": {"type": "string", "format": "date-time"},
            },
            "required": ["email"],
        },
        _implementation=_db_wrapper(analysis_tools.get_staff_ticket_report),
    ),
    Tool(
        name="wait_usr",
        description="Tickets waiting on user",
        inputSchema={"type": "object", "properties": {}, "required": []},
        _implementation=_db_wrapper(analysis_tools.tickets_waiting_on_user),
    ),
    Tool(
        name="sla_brch",
        description="Count SLA breaches",
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
        name="t_trend",
        description="Ticket trend",
        inputSchema={"type": "object", "properties": {"days": {"type": "integer"}}, "required": []},
        _implementation=_db_wrapper(analysis_tools.ticket_trend),
    ),
    Tool(
        name="oc_now",
        description="Get current on-call shift",
        inputSchema={"type": "object", "properties": {}, "required": []},
        _implementation=_db_wrapper(oncall_tools.get_current_oncall),
    ),
    Tool(
        name="oc_sched",
        description="List on-call schedule",
        inputSchema={"type": "object", "properties": {"skip": {"type": "integer"}, "limit": {"type": "integer"}}, "required": []},
        _implementation=_db_wrapper(oncall_tools.list_oncall_schedule),
    ),
    Tool(
        name="user_eml",
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

