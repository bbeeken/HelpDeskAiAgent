import pytest

from src.mcp_server import create_enhanced_server
from src.tool_list import TOOLS


@pytest.mark.asyncio
async def test_enhanced_server_tools():
    server = create_enhanced_server()
    assert getattr(server, "is_enhanced", False)
    assert len(TOOLS) >= 14
    names = [t.name for t in TOOLS]
    assert "ai_suggest_response" not in names
