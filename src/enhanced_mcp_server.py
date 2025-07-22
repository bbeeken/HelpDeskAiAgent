"""Configuration management for the MCP server and stub MCP server helpers."""

from __future__ import annotations

import json
import os
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

import anyio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from .mcp_server import Tool

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    max_retries: int = 3
    retry_base_delay: float = 0.1
    retry_backoff_factor: int = 2
    session_timeout: int = 300  # seconds
    pool_size: int = 10
    max_overflow: int = 20
    pool_pre_ping: bool = True


@dataclass
class ServerConfig:
    """Main server configuration."""
    name: str = "helpdesk-ai-agent"
    version: str = "1.0.0"
    default_limit: int = 10
    max_limit: int = 1000
    enable_metrics: bool = True
    enable_health_check: bool = True


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


@dataclass
class SecurityConfig:
    """Security and validation configuration."""
    enable_rate_limiting: bool = True
    max_requests_per_minute: int = 100
    max_requests_per_hour: int = 1000
    require_authentication: bool = False
    allowed_origins: List[str] = field(default_factory=list)


@dataclass
class MCPServerConfig:
    """Complete MCP server configuration."""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    @classmethod
    def from_env(cls) -> 'MCPServerConfig':
        """Create configuration from environment variables."""
        config = cls()
        
        # Database settings
        config.database.max_retries = int(os.getenv('DB_MAX_RETRIES', config.database.max_retries))
        config.database.retry_base_delay = float(os.getenv('DB_RETRY_DELAY', config.database.retry_base_delay))
        config.database.session_timeout = int(os.getenv('DB_SESSION_TIMEOUT', config.database.session_timeout))
        config.database.pool_size = int(os.getenv('DB_POOL_SIZE', config.database.pool_size))
        
        # Server settings
        config.server.name = os.getenv('SERVER_NAME', config.server.name)
        config.server.default_limit = int(os.getenv('DEFAULT_LIMIT', config.server.default_limit))
        config.server.max_limit = int(os.getenv('MAX_LIMIT', config.server.max_limit))
        config.server.enable_metrics = os.getenv('ENABLE_METRICS', 'true').lower() == 'true'
        
        # Logging settings
        config.logging.level = os.getenv('LOG_LEVEL', config.logging.level)
        config.logging.file_path = os.getenv('LOG_FILE_PATH')
        
        # Security settings
        config.security.enable_rate_limiting = os.getenv('ENABLE_RATE_LIMITING', 'true').lower() == 'true'
        config.security.max_requests_per_minute = int(os.getenv('MAX_REQUESTS_PER_MINUTE', config.security.max_requests_per_minute))
        config.security.require_authentication = os.getenv('REQUIRE_AUTH', 'false').lower() == 'true'
        
        allowed_origins = os.getenv('ALLOWED_ORIGINS', '')
        if allowed_origins:
            config.security.allowed_origins = [origin.strip() for origin in allowed_origins.split(',')]
        
        return config
    
    def validate(self) -> None:
        """Validate configuration settings."""
        if self.server.max_limit <= 0:
            raise ValueError("max_limit must be positive")
        
        if self.server.default_limit <= 0:
            raise ValueError("default_limit must be positive")
        
        if self.server.default_limit > self.server.max_limit:
            raise ValueError("default_limit cannot exceed max_limit")
        
        if self.database.max_retries <= 0:
            raise ValueError("max_retries must be positive")
        
        if self.database.retry_base_delay <= 0:
            raise ValueError("retry_base_delay must be positive")
        
        if self.logging.level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            raise ValueError(f"Invalid log level: {self.logging.level}")


# Global configuration instance
_config: Optional[MCPServerConfig] = None


def get_config() -> MCPServerConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = MCPServerConfig.from_env()
        _config.validate()
    return _config


def set_config(config: MCPServerConfig) -> None:
    """Set the global configuration instance."""
    global _config
    config.validate()
    _config = config


# ---------------------------------------------------------------------------
# MCP server tool configuration
# ---------------------------------------------------------------------------

from datetime import datetime, timezone
from typing import Any, Dict as _Dict
import json
from mcp import types

from src.infrastructure import database as db
from src.core.services.ticket_management import TicketManager
from src.core.services.reference_data import ReferenceDataManager
from src.shared.schemas.ticket import TicketExpandedOut, TicketCreate
from src.core.services.analytics_reporting import (
    open_tickets_by_site,
    open_tickets_by_user,
    tickets_by_status,
    ticket_trend,
    sla_breaches,
)
from src.core.services.enhanced_context import EnhancedContextManager


async def _get_ticket(ticket_id: int) -> _Dict[str, Any]:
    """Retrieve a ticket by ID and return full details."""
    try:
        async with db.SessionLocal() as db_session:
            ticket = await TicketManager().get_ticket(db_session, ticket_id)
            if not ticket:
                return {"status": "error", "error": "Ticket not found"}
            data = TicketExpandedOut.model_validate(ticket).model_dump()
            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in get_ticket: {e}")
        return {"status": "error", "error": str(e)}


async def _list_tickets(
    limit: int = 10,
    skip: int = 0,
    filters: _Dict[str, Any] | None = None,
    sort: list[str] | None = None,
) -> _Dict[str, Any]:
    """List tickets with optional filtering."""
    try:
        async with db.SessionLocal() as db_session:
            tickets = await TicketManager().list_tickets(
                db_session,
                filters=filters or None,
                skip=skip,
                limit=limit,
                sort=sort,
            )
            data = [
                TicketExpandedOut.model_validate(t).model_dump() for t in tickets
            ]
            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in list_tickets: {e}")
        return {"status": "error", "error": str(e)}


async def _get_tickets_by_user(
    identifier: str,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    filters: _Dict[str, Any] | None = None,
) -> _Dict[str, Any]:
    """Return tickets associated with a user."""
    try:
        async with db.SessionLocal() as db_session:
            tickets = await TicketManager().get_tickets_by_user(
                db_session,
                identifier,
                skip=skip,
                limit=limit,
                status=status,
                filters=filters,
            )
            data = [
                TicketExpandedOut.model_validate(t).model_dump() for t in tickets
            ]
            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in get_tickets_by_user: {e}")
        return {"status": "error", "error": str(e)}


async def _search_tickets(query: str, limit: int = 10) -> _Dict[str, Any]:
    """Search tickets by text query."""
    try:
        async with db.SessionLocal() as db_session:
            results = await TicketManager().search_tickets(
                db_session, query, limit=limit
            )
            return {"status": "success", "data": results}
    except Exception as e:
        logger.error(f"Error in search_tickets: {e}")
        return {"status": "error", "error": str(e)}


async def _create_ticket(**payload: Any) -> _Dict[str, Any]:
    """Create a new ticket and return the created record."""
    try:
        async with db.SessionLocal() as db_session:
            payload.setdefault("Created_Date", datetime.now(timezone.utc))
            payload.setdefault("LastModified", datetime.now(timezone.utc))
            result = await TicketManager().create_ticket(db_session, payload)
            await db_session.commit()
            if not result.success:
                raise Exception(result.error or "create failed")
            await db_session.commit()
            ticket = await TicketManager().get_ticket(
                db_session, result.data.Ticket_ID
            )
            data = TicketExpandedOut.model_validate(ticket).model_dump()
            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in create_ticket: {e}")
        return {"status": "error", "error": str(e)}


async def _update_ticket(ticket_id: int, updates: _Dict[str, Any]) -> _Dict[str, Any]:
    """Update an existing ticket."""
    try:
        async with db.SessionLocal() as db_session:
            updated = await TicketManager().update_ticket(db_session, ticket_id, updates)
            await db_session.commit()
            if not updated:
                return {"status": "error", "error": "Ticket not found"}
            await db_session.commit()
            ticket = await TicketManager().get_ticket(db_session, ticket_id)
            data = TicketExpandedOut.model_validate(ticket).model_dump()
            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in update_ticket: {e}")
        return {"status": "error", "error": str(e)}


async def _close_ticket(
    ticket_id: int,
    resolution: str,
    status_id: int = 4,
) -> _Dict[str, Any]:
    """Close a ticket with a resolution."""
    try:
        async with db.SessionLocal() as db_session:
            updates = {
                "Ticket_Status_ID": status_id,
                "Resolution": resolution,
                "Closed_Date": datetime.now(timezone.utc),
            }
            updated = await TicketManager().update_ticket(db_session, ticket_id, updates)
            await db_session.commit()
            if not updated:
                return {"status": "error", "error": "Ticket not found"}
            await db_session.commit()
            ticket = await TicketManager().get_ticket(db_session, ticket_id)
            data = TicketExpandedOut.model_validate(ticket).model_dump()
            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in close_ticket: {e}")
        return {"status": "error", "error": str(e)}


async def _assign_ticket(
    ticket_id: int,
    assignee_email: str,
    assignee_name: str | None = None,
) -> _Dict[str, Any]:
    """Assign a ticket to a technician."""
    try:
        async with db.SessionLocal() as db_session:
            updates = {
                "Assigned_Email": assignee_email,
                "Assigned_Name": assignee_name or assignee_email,
            }
            updated = await TicketManager().update_ticket(db_session, ticket_id, updates)
            await db_session.commit()
            if not updated:
                return {"status": "error", "error": "Ticket not found"}
            await db_session.commit()
            ticket = await TicketManager().get_ticket(db_session, ticket_id)
            data = TicketExpandedOut.model_validate(ticket).model_dump()
            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in assign_ticket: {e}")
        return {"status": "error", "error": str(e)}


async def _add_ticket_message(
    ticket_id: int,
    message: str,
    sender_name: str,
    sender_code: str | None = None,
) -> _Dict[str, Any]:
    """Add a message to a ticket."""
    try:
        async with db.SessionLocal() as db_session:
            created = await TicketManager().post_message(
                db_session,
                ticket_id,
                message,
                sender_code or sender_name,
                sender_name,
            )
            return {
                "status": "success",
                "data": {
                    "id": created.ID,
                    "ticket_id": created.Ticket_ID,
                    "message": created.Message,
                },
            }
    except Exception as e:
        logger.error(f"Error in add_ticket_message: {e}")
        return {"status": "error", "error": str(e)}


async def _get_ticket_messages(ticket_id: int) -> _Dict[str, Any]:
    """Return messages for a ticket with message length."""
    try:
        async with db.SessionLocal() as db_session:
            msgs = await TicketManager().get_messages(db_session, ticket_id)
            data = [
                {
                    "ID": m.ID,
                    "Ticket_ID": m.Ticket_ID,
                    "Message": m.Message,
                    "SenderUserCode": m.SenderUserCode,
                    "SenderUserName": m.SenderUserName,
                    "DateTimeStamp": m.DateTimeStamp,
                    "message_length": len(m.Message or ""),
                }
                for m in msgs
            ]
            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in get_ticket_messages: {e}")
        return {"status": "error", "error": str(e)}


async def _get_ticket_attachments(ticket_id: int) -> _Dict[str, Any]:
    """Return attachments for a ticket with file type."""
    try:
        async with db.SessionLocal() as db_session:
            atts = await TicketManager().get_attachments(db_session, ticket_id)
            data = [
                {
                    "ID": a.ID,
                    "Ticket_ID": a.Ticket_ID,
                    "Name": a.Name,
                    "WebURl": a.WebURl,
                    "UploadDateTime": a.UploadDateTime,
                    "file_type": os.path.splitext(a.Name)[1].lstrip(".").lower(),
                }
                for a in atts
            ]
            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in get_ticket_attachments: {e}")
        return {"status": "error", "error": str(e)}


async def _get_open_tickets(
    days: int = 3650,
    limit: int = 10,
    skip: int = 0,
    filters: _Dict[str, Any] | None = None,
    sort: list[str] | None = None,
) -> _Dict[str, Any]:
    """Return open tickets with optional filters and sorting."""
    try:
        async with db.SessionLocal() as db_session:
            tickets = await TicketManager().get_tickets_by_timeframe(
                db_session,
                status="open",
                days=days,
                limit=limit + skip if limit else None,
            )

            if filters:
                filtered = []
                for t in tickets:
                    match = True
                    for k, v in filters.items():
                        if hasattr(t, k) and getattr(t, k) != v:
                            match = False
                            break
                    if match:
                        filtered.append(t)
                tickets = filtered

            if sort:
                for key in reversed(sort):
                    direction = "asc"
                    column = key
                    if key.startswith("-"):
                        column = key[1:]
                        direction = "desc"
                    elif " " in key:
                        column, dir_part = key.rsplit(" ", 1)
                        if dir_part.lower() in {"asc", "desc"}:
                            direction = dir_part.lower()
                    if tickets and hasattr(tickets[0], column):
                        tickets.sort(
                            key=lambda t: getattr(t, column),
                            reverse=direction == "desc",
                        )

            if skip:
                tickets = tickets[skip:]
            if limit:
                tickets = tickets[:limit]

            data = [TicketExpandedOut.model_validate(t).model_dump() for t in tickets]
            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in get_open_tickets: {e}")
        return {"status": "error", "error": str(e)}


async def _get_analytics(type: str, params: _Dict[str, Any] | None = None) -> _Dict[str, Any]:
    """Return analytics data based on requested type."""
    try:
        async with db.SessionLocal() as db_session:
            if type == "status_counts":
                result = await tickets_by_status(db_session)
                data = result.data if getattr(result, "success", True) else []
            elif type == "site_counts":
                data = await open_tickets_by_site(db_session)
            elif type == "technician_workload":
                data = await open_tickets_by_user(db_session, params or None)
            elif type == "sla_breaches":
                days = params.get("sla_days", 2) if params else 2
                status_ids = params.get("status_ids") if params else None
                data = {
                    "breaches": await sla_breaches(
                        db_session, sla_days=days, status_ids=status_ids, filters=params
                    )
                }
            elif type == "trends":
                days = params.get("days", 7) if params else 7
                data = await ticket_trend(db_session, days)
            else:
                raise ValueError("unknown analytics type")
            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in get_analytics: {e}")
        return {"status": "error", "error": str(e)}


async def _list_reference_data(
    type: str,
    limit: int = 10,
    filters: _Dict[str, Any] | None = None,
    sort: list[str] | None = None,
) -> _Dict[str, Any]:
    """Return reference data such as sites or assets."""
    try:
        async with db.SessionLocal() as db_session:
            mgr = ReferenceDataManager()
            if type == "sites":
                records = await mgr.list_sites(
                    db_session, limit=limit, filters=filters or None, sort=sort
                )
            elif type == "assets":
                records = await mgr.list_assets(
                    db_session, limit=limit, filters=filters or None, sort=sort
                )
            elif type == "vendors":
                records = await mgr.list_vendors(
                    db_session, limit=limit, filters=filters or None, sort=sort
                )
            elif type == "categories":
                records = await mgr.list_categories(
                    db_session, filters=filters or None, sort=sort
                )
            else:
                raise ValueError("unknown reference data type")
            data = [r.__dict__ for r in records]
            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error in list_reference_data: {e}")
        return {"status": "error", "error": str(e)}


async def _ticket_full_context(ticket_id: int) -> _Dict[str, Any]:
    """Return extended context for a ticket."""
    try:
        async with db.SessionLocal() as db_session:
            mgr = EnhancedContextManager(db_session)
            context = await mgr.get_ticket_full_context(ticket_id)
            return {"status": "success", "data": context}
    except Exception as e:
        logger.error(f"Error in get_ticket_full_context: {e}")
        return {"status": "error", "error": str(e)}


async def _system_snapshot() -> _Dict[str, Any]:
    """Return overall system snapshot."""
    try:
        async with db.SessionLocal() as db_session:
            mgr = EnhancedContextManager(db_session)
            snapshot = await mgr.get_system_snapshot()
            return {"status": "success", "data": snapshot}
    except Exception as e:
        logger.error(f"Error in get_system_snapshot: {e}")
        return {"status": "error", "error": str(e)}


ENHANCED_TOOLS: List[Tool] = [
    Tool(
        name="get_ticket",
        description="Get a ticket by ID",
        inputSchema={
            "type": "object",
            "properties": {"ticket_id": {"type": "integer"}},
            "required": ["ticket_id"],
        },
        _implementation=_get_ticket,
    ),
    Tool(
        name="list_tickets",
        description="List tickets with optional filters",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10},
                "skip": {"type": "integer", "default": 0},
                "filters": {"type": "object"},
                "sort": {"type": "array", "items": {"type": "string"}},
            },
        },
        _implementation=_list_tickets,
    ),
    Tool(
        name="create_ticket",
        description="Create a new ticket",
        inputSchema=TicketCreate.model_json_schema(),
        _implementation=_create_ticket,
    ),
    Tool(
        name="update_ticket",
        description="Update an existing ticket",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer"},
                "updates": {"type": "object"},
            },
            "required": ["ticket_id", "updates"],
        },
        _implementation=_update_ticket,
    ),
    Tool(
        name="close_ticket",
        description="Close a ticket with resolution",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer"},
                "resolution": {"type": "string"},
                "status_id": {"type": "integer", "default": 4},
            },
            "required": ["ticket_id", "resolution"],
        },
        _implementation=_close_ticket,
    ),
    Tool(
        name="assign_ticket",
        description="Assign a ticket to a technician",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer"},
                "assignee_email": {"type": "string"},
                "assignee_name": {"type": "string"},
            },
            "required": ["ticket_id", "assignee_email"],
        },
        _implementation=_assign_ticket,
    ),
    Tool(
        name="add_ticket_message",
        description="Add a message to a ticket",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer"},
                "message": {"type": "string"},
                "sender_name": {"type": "string"},
                "sender_code": {"type": "string"},
            },
            "required": ["ticket_id", "message", "sender_name"],
        },
        _implementation=_add_ticket_message,
    ),
    Tool(
        name="get_ticket_messages",
        description="Retrieve messages for a ticket",
        inputSchema={
            "type": "object",
            "properties": {"ticket_id": {"type": "integer"}},
            "required": ["ticket_id"],
        },
        _implementation=_get_ticket_messages,
    ),
    Tool(
        name="get_ticket_attachments",
        description="Retrieve attachments for a ticket",
        inputSchema={
            "type": "object",
            "properties": {"ticket_id": {"type": "integer"}},
            "required": ["ticket_id"],
        },
        _implementation=_get_ticket_attachments,
    ),
    Tool(
        name="search_tickets",
        description="Search tickets",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
        _implementation=_search_tickets,
    ),
    Tool(
        name="get_tickets_by_user",
        description="Retrieve tickets associated with a user",
        inputSchema={
            "type": "object",
            "properties": {
                "identifier": {"type": "string"},
                "skip": {"type": "integer", "default": 0},
                "limit": {"type": "integer", "default": 100},
                "status": {"type": "string"},
                "filters": {"type": "object"},
            },
            "required": ["identifier"],
        },
        _implementation=_get_tickets_by_user,
    ),
    Tool(
        name="get_open_tickets",
        description="List open tickets with optional filters",
        inputSchema={
            "type": "object",
            "properties": {
                "days": {"type": "integer", "default": 3650},
                "limit": {"type": "integer", "default": 10},
                "skip": {"type": "integer", "default": 0},
                "filters": {"type": "object"},
                "sort": {"type": "array", "items": {"type": "string"}},
            },
        },
        _implementation=_get_open_tickets,
    ),
    Tool(
        name="get_analytics",
        description="Retrieve analytics information",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                "params": {"type": "object"},
            },
            "required": ["type"],
        },
        _implementation=_get_analytics,
    ),
    Tool(
        name="list_reference_data",
        description="List reference data like sites or assets",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
                "filters": {"type": "object"},
                "sort": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["type"],
        },
        _implementation=_list_reference_data,
    ),
    Tool(
        name="get_ticket_full_context",
        description="Full context for a ticket",
        inputSchema={
            "type": "object",
            "properties": {"ticket_id": {"type": "integer"}},
            "required": ["ticket_id"],
        },
        _implementation=_ticket_full_context,
    ),
    Tool(
        name="get_system_snapshot",
        description="System snapshot",
        inputSchema={},
        _implementation=_system_snapshot,
    ),
]


def create_server() -> Server:
    """Instantiate a Server and register tools."""

    server = Server("helpdesk-ai-agent")

    @server.list_tools()
    async def _list_tools() -> List[types.Tool]:
        return [
            types.Tool(
                name=t.name,
                description=t.description,
                inputSchema=t.inputSchema,
            )
            for t in ENHANCED_TOOLS
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict | None) -> list:
        tool = next((t for t in ENHANCED_TOOLS if t.name == name), None)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
        args = arguments or {}
        result = await tool._implementation(**args)
        return [types.TextContent(type="text", text=json.dumps(result, default=str))]

    return server


def run_server() -> None:
    """Run the MCP server with stdio transport."""
    async def _main() -> None:
        server = create_server()
        async with stdio_server() as (read, write):
            await server.run(read, write)

    anyio.run(_main)


__all__ = ["MCPServerConfig", "get_config", "set_config", "ENHANCED_TOOLS", "create_server", "run_server"]