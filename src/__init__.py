"""HelpDesk MCP Server"""

__version__ = "1.0.0"

from .mcp_server import Tool, create_server, run_server
from mcp.server import Server

__all__ = ["Tool", "Server", "create_server", "run_server"]
