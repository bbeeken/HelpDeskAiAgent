import pytest

from src.mcp_server import create_enhanced_server
from src.tool_list import TOOLS


@pytest.mark.asyncio
async def test_enhanced_server_tools(monkeypatch):
    async def fake(ticket, context=""):
        return {"ok": True}

    monkeypatch.setattr("tools.ai_tools.ai_suggest_response", fake)

    server = create_enhanced_server()
    assert getattr(server, "is_enhanced", False)
    assert len(TOOLS) >= 20
    names = [t.name for t in TOOLS]
    assert "ai_suggest_response" in names

    tool = next(t for t in TOOLS if t.name == "ai_suggest_response")
    tool._implementation = fake
    result = await tool._implementation(ticket={})
    assert result == {"ok": True}
