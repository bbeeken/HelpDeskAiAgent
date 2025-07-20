"""Configuration management for the MCP server and stub MCP server helpers."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

import anyio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from .mcp_server import Tool


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

from datetime import datetime
from typing import Any, Dict as _Dict
import json
from mcp import types

from src.infrastructure import database as db
from src.core.services.ticket_management import TicketManager
from src.core.services.reference_data import ReferenceDataManager
from src.core.services.analytics_reporting import (
    open_tickets_by_site,
    open_tickets_by_user,
    tickets_by_status,
    ticket_trend,
    tickets_waiting_on_user,
    sla_breaches,
    get_staff_ticket_report,
)
from src.core.services.enhanced_context import EnhancedContextManager


async def _g_ticket(ticket_id: int) -> _Dict[str, Any] | None:
    """Fetch a single ticket by ID.

    Parameters
    ----------
    ticket_id:
        The ID of the ticket to retrieve.

    Returns
    -------
    dict | None
        A dictionary containing ``ticket_id`` if the ticket exists, otherwise
        ``None``.
    """
    async with db.SessionLocal() as db_session:
        ticket = await TicketManager().get_ticket(db_session, ticket_id)
        return {"ticket_id": ticket.Ticket_ID} if ticket else None


async def _l_tkts(limit: int = 10) -> list[_Dict[str, Any]]:
    """List the most recent tickets.

    Parameters
    ----------
    limit:
        Maximum number of tickets to return. Defaults to ``10``.

    Returns
    -------
    list[dict]
        A list of dictionaries, each containing ``ticket_id`` for a ticket.
    """
    async with db.SessionLocal() as db_session:
        tickets = await TicketManager().list_tickets(db_session, limit=limit)
        return [{"ticket_id": t.Ticket_ID} for t in tickets]


async def _tickets_by_user(
    identifier: str,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    filters: _Dict[str, Any] | None = None,
) -> list[Any]:
    async with db.SessionLocal() as db_session:
        return await TicketManager().get_tickets_by_user(
            db_session,
            identifier,
            skip=skip,
            limit=limit,
            status=status,
            filters=filters,
        )


async def _open_by_site() -> list[Any]:
    async with db.SessionLocal() as db_session:
        return await open_tickets_by_site(db_session)


async def _open_by_assigned_user(filters: _Dict[str, Any] | None = None) -> list[Any]:
    async with db.SessionLocal() as db_session:
        return await open_tickets_by_user(db_session, filters)


async def _tickets_status() -> list[Any]:
    async with db.SessionLocal() as db_session:
        result = await tickets_by_status(db_session)
        return result.data if getattr(result, "success", True) else []


async def _ticket_trend(days: int = 7) -> list[Any]:
    async with db.SessionLocal() as db_session:
        return await ticket_trend(db_session, days)


async def _waiting_on_user() -> list[Any]:
    async with db.SessionLocal() as db_session:
        return await tickets_waiting_on_user(db_session)


async def _sla_breaches(days: int = 2) -> int:
    async with db.SessionLocal() as db_session:
        return await sla_breaches(db_session, sla_days=days)


async def _staff_report(
    assigned_email: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> Any:
    async with db.SessionLocal() as db_session:
        return await get_staff_ticket_report(
            db_session,
            assigned_email,
            start_date=start_date,
            end_date=end_date,
        )


async def _tickets_by_timeframe(
    status: str | None = None,
    days: int = 7,
    limit: int = 10,
) -> list[Any]:
    async with db.SessionLocal() as db_session:
        return await TicketManager().get_tickets_by_timeframe(
            db_session,
            status=status,
            days=days,
            limit=limit,
        )


async def _search_tickets(query: str, limit: int = 10) -> list[Any]:
    async with db.SessionLocal() as db_session:
        return await TicketManager().search_tickets(db_session, query, limit=limit)


async def _list_sites(limit: int = 10) -> list[Any]:
    async with db.SessionLocal() as db_session:
        return await ReferenceDataManager().list_sites(db_session, limit=limit)


async def _list_assets(limit: int = 10) -> list[Any]:
    async with db.SessionLocal() as db_session:
        return await ReferenceDataManager().list_assets(db_session, limit=limit)


async def _list_vendors(limit: int = 10) -> list[Any]:
    async with db.SessionLocal() as db_session:
        return await ReferenceDataManager().list_vendors(db_session, limit=limit)


async def _list_categories() -> list[Any]:
    async with db.SessionLocal() as db_session:
        return await ReferenceDataManager().list_categories(db_session)


async def _ticket_full_context(ticket_id: int) -> Any:
    async with db.SessionLocal() as db_session:
        mgr = EnhancedContextManager(db_session)
        return await mgr.get_ticket_full_context(ticket_id)


async def _system_snapshot() -> Any:
    async with db.SessionLocal() as db_session:
        mgr = EnhancedContextManager(db_session)
        return await mgr.get_system_snapshot()


ENHANCED_TOOLS: List[Tool] = [
    Tool(
        name="g_ticket",
        description="Get a ticket by ID",
        inputSchema={
            "type": "object",
            "properties": {"ticket_id": {"type": "integer"}},
            "required": ["ticket_id"],
        },
        _implementation=_g_ticket,
    ),
    Tool(
        name="l_tkts",
        description="List recent tickets",
        inputSchema={
            "type": "object",
            "properties": {"limit": {"type": "integer"}},
        },
        _implementation=_l_tkts,
    ),
    Tool(
        name="tickets_by_user",
        description="List tickets for a user",
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
        _implementation=_tickets_by_user,
    ),
    Tool(
        name="by_user",
        description="Alias of tickets_by_user",
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
        _implementation=_tickets_by_user,
    ),
    Tool("open_by_site", "Open tickets by site", {}, _open_by_site),
    Tool(
        "open_by_assigned_user",
        "Open tickets by technician",
        {"type": "object", "properties": {"filters": {"type": "object"}}},
        _open_by_assigned_user,
    ),
    Tool("tickets_by_status", "Ticket counts by status", {}, _tickets_status),
    Tool(
        "ticket_trend",
        "Ticket trend information",
        {"type": "object", "properties": {"days": {"type": "integer"}}},
        _ticket_trend,
    ),
    Tool("waiting_on_user", "Tickets waiting on user", {}, _waiting_on_user),
    Tool(
        "sla_breaches",
        "Count of SLA breaches",
        {"type": "object", "properties": {"days": {"type": "integer"}}},
        _sla_breaches,
    ),
    Tool(
        "staff_report",
        "Technician ticket report",
        {
            "type": "object",
            "properties": {
                "assigned_email": {"type": "string"},
                "start_date": {"type": "string", "format": "date-time"},
                "end_date": {"type": "string", "format": "date-time"},
            },
            "required": ["assigned_email"],
        },
        _staff_report,
    ),
    Tool(
        "tickets_by_timeframe",
        "Tickets by status and age",
        {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "days": {"type": "integer"},
                "limit": {"type": "integer"},
            },
        },
        _tickets_by_timeframe,
    ),
    Tool(
        "search_tickets",
        "Search tickets",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
        _search_tickets,
    ),
    Tool("list_sites", "List sites", {"type": "object", "properties": {"limit": {"type": "integer"}}}, _list_sites),
    Tool("list_assets", "List assets", {"type": "object", "properties": {"limit": {"type": "integer"}}}, _list_assets),
    Tool("list_vendors", "List vendors", {"type": "object", "properties": {"limit": {"type": "integer"}}}, _list_vendors),
    Tool("list_categories", "List categories", {}, _list_categories),
    Tool("get_ticket_full_context", "Full context for a ticket", {"type": "object", "properties": {"ticket_id": {"type": "integer"}}, "required": ["ticket_id"]}, _ticket_full_context),
    Tool("get_system_snapshot", "System snapshot", {}, _system_snapshot),
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