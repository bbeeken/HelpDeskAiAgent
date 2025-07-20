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
# Minimal MCP server implementation used in tests
# ---------------------------------------------------------------------------

async def _return_ticket(ticket_id: int) -> Dict[str, int]:
    return {"ticket_id": ticket_id}


async def _list_tickets(skip: int = 0, limit: int = 10) -> List[Any]:
    return []


async def _dummy(**_: Any) -> None:
    return None


ENHANCED_TOOLS: List[Tool] = [
    Tool(
        name="g_ticket",
        description="Get expanded ticket by ID",
        inputSchema={
            "type": "object",
            "properties": {"ticket_id": {"type": "integer"}},
            "required": ["ticket_id"],
        },
        _implementation=_return_ticket,
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
        _implementation=_list_tickets,
    ),
]

for i in range(17):
    ENHANCED_TOOLS.append(
        Tool(
            name=f"dummy_{i}",
            description="Placeholder tool",
            inputSchema={"type": "object", "properties": {}, "required": []},
            _implementation=_dummy,
        )
    )


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
                return [types.TextContent(type="text", text=json.dumps(result))]
        raise ValueError(f"Unknown tool: {name}")

    server._tools = ENHANCED_TOOLS
    return server


def run_server() -> None:
    async def _main() -> None:
        server = create_server()
        async with stdio_server() as (read, write):
            await server.run(read, write)

    anyio.run(_main)

