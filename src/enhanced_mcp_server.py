from __future__ import annotations


from typing import Any, Awaitable, Callable, Dict, Iterable, List

import json
import anyio
import logging
from mcp.server.stdio import stdio_server

from mcp.server import Server
from mcp import types

from src.infrastructure.database import SessionLocal
from .mcp_server import Tool
from src.shared.exceptions import ValidationError, DatabaseError

logger = logging.getLogger(__name__)

# Business logic modules
from src.core.services.ticket_management import TicketManager, TicketTools
from src.core.services.reference_data import ReferenceDataManager
from src.core.services.user_services import UserManager
from src.core.services.analytics_reporting import (
    tickets_by_status,
    open_tickets_by_site,
    open_tickets_by_user,
    get_staff_ticket_report,
    sla_breaches,
    ticket_trend,
    tickets_waiting_on_user,
)


async def _with_session(func: Callable[..., Awaitable[Any]], **kwargs: Any) -> Any:
    async with SessionLocal() as db:
        return await func(db, **kwargs)


def _db_wrapper(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    async def wrapper(**kwargs: Any) -> Any:
        return await _with_session(func, **kwargs)

    return wrapper


def _safe_tool_wrapper(func: Callable[..., Awaitable[Any]]):
    async def wrapper(**kwargs: Any):
        try:
            return await _with_session(func, **kwargs)
        except ValidationError as e:
            return {"error": "validation_error", "details": str(e)}
        except DatabaseError as e:
            return {"error": "database_error", "details": str(e)}
        except Exception:
            logger.exception("Tool execution failed: %s", func.__name__)
            return {"error": "internal_error", "details": "Tool execution failed"}

    return wrapper


async def _search_tickets_smart(
    db: Any,
    query: str,
    limit: int = 10,
    include_closed: bool = False,
    filters: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Helper to call :meth:`TicketTools.search_tickets_smart`."""
    tools = TicketTools(db)
    return await tools.search_tickets_smart(
        query=query,
        filters=filters,
        limit=limit,
        include_closed=include_closed,
    )


async def _open_tickets_by_user_tool(db: Any, **kwargs: Any) -> Any:
    """Pass kwargs as filters to open_tickets_by_user."""
    filters = kwargs or None
    return await open_tickets_by_user(db, filters=filters)


ENHANCED_TOOLS: List[Tool] = [
    Tool(
        name="g_asset",
        description="Retrieve an asset by ID",
        inputSchema={"type": "object", "properties": {"asset_id": {"type": "integer"}}, "required": ["asset_id"]},
        _implementation=_safe_tool_wrapper(lambda db, asset_id: ReferenceDataManager().get_asset(db, asset_id)),
    ),
    Tool(
        name="l_assets",
        description="List assets",
        inputSchema={
            "type": "object",
            "properties": {
                "skip": {"type": "integer"},
                "limit": {"type": "integer"},
                "filters": {"type": "object"},
                "sort": {"type": "array", "items": {"type": "string"}},
            },
            "required": [],
        },
        _implementation=_safe_tool_wrapper(lambda db, **kwargs: ReferenceDataManager().list_assets(db, **kwargs)),
    ),
    Tool(
        name="g_vendor",
        description="Retrieve a vendor by ID",
        inputSchema={"type": "object", "properties": {"vendor_id": {"type": "integer"}}, "required": ["vendor_id"]},
        _implementation=_safe_tool_wrapper(lambda db, vendor_id: ReferenceDataManager().get_vendor(db, vendor_id)),
    ),
    Tool(
        name="l_vends",
        description="List vendors",
        inputSchema={
            "type": "object",
            "properties": {
                "skip": {"type": "integer"},
                "limit": {"type": "integer"},
                "filters": {"type": "object"},
                "sort": {"type": "array", "items": {"type": "string"}},
            },
            "required": [],
        },
        _implementation=_safe_tool_wrapper(lambda db, **kwargs: ReferenceDataManager().list_vendors(db, **kwargs)),
    ),
    Tool(
        name="g_site",
        description="Retrieve a site by ID",
        inputSchema={"type": "object", "properties": {"site_id": {"type": "integer"}}, "required": ["site_id"]},
        _implementation=_safe_tool_wrapper(lambda db, site_id: ReferenceDataManager().get_site(db, site_id)),
    ),
    Tool(
        name="l_sites",
        description="List sites",
        inputSchema={
            "type": "object",
            "properties": {
                "skip": {"type": "integer"},
                "limit": {"type": "integer"},
                "filters": {"type": "object"},
                "sort": {"type": "array", "items": {"type": "string"}},
            },
            "required": [],
        },
        _implementation=_safe_tool_wrapper(lambda db, **kwargs: ReferenceDataManager().list_sites(db, **kwargs)),
    ),
    Tool(
        name="l_cats",
        description="List ticket categories",
        inputSchema={
            "type": "object",
            "properties": {
                "filters": {"type": "object"},
                "sort": {"type": "array", "items": {"type": "string"}},
            },
            "required": [],
        },
        _implementation=_safe_tool_wrapper(lambda db, **kwargs: ReferenceDataManager().list_categories(db, **kwargs)),
    ),
    Tool(
        name="l_status",
        description="List ticket statuses",
        inputSchema={
            "type": "object",
            "properties": {
                "filters": {"type": "object"},
                "sort": {"type": "array", "items": {"type": "string"}},
            },
            "required": [],
        },
        _implementation=_safe_tool_wrapper(lambda db, **kwargs: ReferenceDataManager().list_statuses(db, **kwargs)),
    ),
    Tool(
        name="g_ticket",
        description="Get expanded ticket by ID",
        inputSchema={"type": "object", "properties": {"ticket_id": {"type": "integer"}}, "required": ["ticket_id"]},
        _implementation=_safe_tool_wrapper(lambda db, ticket_id: TicketManager().get_ticket(db, ticket_id)),
    ),
    Tool(
        name="l_tkts",
        description="List expanded tickets",
        inputSchema={
            "type": "object",
            "properties": {
                "skip": {"type": "integer"},
                "limit": {"type": "integer"},
                "filters": {"type": "object"},
                "sort": {"type": "array", "items": {"type": "string"}},
            },
            "required": [],
        },
        _implementation=_safe_tool_wrapper(lambda db, **kwargs: TicketManager().list_tickets(db, **kwargs)),
    ),
    Tool(
        name="s_tkts",
        description="Search tickets",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
                "params": {"type": "object"},
            },
            "required": ["query"],
        },
        _implementation=_safe_tool_wrapper(lambda db, query, limit=10, params=None: TicketManager().search_tickets(db, query, limit=limit, params=params)),
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
        _implementation=_safe_tool_wrapper(_search_tickets_smart),
    ),
    Tool(
        name="c_ticket",
        description="Create a ticket",
        inputSchema={"type": "object", "properties": {"ticket_obj": {"type": "object"}}, "required": ["ticket_obj"]},
        _implementation=_safe_tool_wrapper(lambda db, ticket_obj: TicketManager().create_ticket(db, ticket_obj)),
    ),
    Tool(
        name="u_ticket",
        description="Update a ticket",
        inputSchema={"type": "object", "properties": {"ticket_id": {"type": "integer"}, "updates": {"type": "object"}}, "required": ["ticket_id", "updates"]},
        _implementation=_safe_tool_wrapper(lambda db, ticket_id, updates: TicketManager().update_ticket(db, ticket_id, updates)),
    ),
    Tool(
        name="d_ticket",
        description="Delete a ticket",
        inputSchema={"type": "object", "properties": {"ticket_id": {"type": "integer"}}, "required": ["ticket_id"]},
        _implementation=_safe_tool_wrapper(lambda db, ticket_id: TicketManager().delete_ticket(db, ticket_id)),
    ),
    Tool(
        name="g_tmsg",
        description="List messages for a ticket",
        inputSchema={"type": "object", "properties": {"ticket_id": {"type": "integer"}}, "required": ["ticket_id"]},
        _implementation=_safe_tool_wrapper(lambda db, ticket_id: TicketManager().get_messages(db, ticket_id)),
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
        _implementation=_safe_tool_wrapper(lambda db, ticket_id, message, sender_code, sender_name: TicketManager().post_message(db, ticket_id, message, sender_code)),
    ),
    Tool(
        name="t_attach",
        description="Get attachments for a ticket",
        inputSchema={"type": "object", "properties": {"ticket_id": {"type": "integer"}}, "required": ["ticket_id"]},
        _implementation=_safe_tool_wrapper(lambda db, ticket_id: TicketManager().get_attachments(db, ticket_id)),
    ),
    Tool(
        name="t_status",
        description="Count tickets by status",
        inputSchema={"type": "object", "properties": {}, "required": []},
        _implementation=_safe_tool_wrapper(tickets_by_status),
    ),
    Tool(
        name="op_site",
        description="Open ticket counts by site",
        inputSchema={"type": "object", "properties": {}, "required": []},
        _implementation=_safe_tool_wrapper(open_tickets_by_site),
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
        _implementation=_safe_tool_wrapper(_open_tickets_by_user_tool),
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
                "status": {"type": "string"},
                "filters": {"type": "object"},
            },
            "required": ["identifier"],
        },
        _implementation=_safe_tool_wrapper(lambda db, identifier, **kwargs: TicketManager().get_tickets_by_user(db, identifier, **kwargs)),
    ),
    Tool(
        name="tickets_by_timeframe",
        description="List tickets by timeframe and status",
        inputSchema={
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "days": {"type": "integer"},
                "limit": {"type": "integer"},
            },
            "required": [],
        },
        _implementation=_safe_tool_wrapper(lambda db, **kwargs: TicketManager().get_tickets_by_timeframe(db, **kwargs)),
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
        _implementation=_safe_tool_wrapper(get_staff_ticket_report),
    ),
    Tool(
        name="wait_usr",
        description="Tickets waiting on user",
        inputSchema={"type": "object", "properties": {}, "required": []},
        _implementation=_safe_tool_wrapper(tickets_waiting_on_user),
    ),
    Tool(
        name="sla_brch",
        description="Count SLA breaches",
        inputSchema={
            "type": "object",
            "properties": {
                "sla_days": {"type": "integer"},
                "filters": {"type": "object"},
                "status_id": {"oneOf": [{"type": "integer"}, {"type": "array", "items": {"type": "integer"}}]},
            },
            "required": [],
        },
        _implementation=_safe_tool_wrapper(sla_breaches),
    ),
    Tool(
        name="t_trend",
        description="Ticket trend",
        inputSchema={"type": "object", "properties": {"days": {"type": "integer"}}, "required": []},
        _implementation=_safe_tool_wrapper(ticket_trend),
    ),
    Tool(
        name="oc_now",
        description="Get current on-call shift",
        inputSchema={"type": "object", "properties": {}, "required": []},
        _implementation=_safe_tool_wrapper(lambda db: UserManager().get_current_oncall(db)),
    ),
    Tool(
        name="oc_sched",
        description="List on-call schedule",
        inputSchema={
            "type": "object",
            "properties": {
                "skip": {"type": "integer"},
                "limit": {"type": "integer"},
                "filters": {"type": "object"},
                "sort": {"type": "array", "items": {"type": "string"}},
            },
            "required": [],
        },
        _implementation=_safe_tool_wrapper(lambda db, **kwargs: UserManager().list_oncall_schedule(db, **kwargs)),
    ),
    Tool(
        name="user_eml",
        description="Look up user information by email",
        inputSchema={"type": "object", "properties": {"email": {"type": "string"}}, "required": ["email"]},
        _implementation=lambda email: UserManager().get_user_by_email(email),
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

