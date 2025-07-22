import pytest

from src.tool_list import TOOLS
import src.core.services.analytics_reporting as analytics_reporting


@pytest.mark.asyncio
async def test_tool_count():
    assert len(TOOLS) >= 14


def test_schema_quality():
    for tool in TOOLS:
        assert isinstance(tool.inputSchema, dict)
        if tool.inputSchema:
            assert tool.inputSchema.get("type") == "object"


def test_semantic_filter_support():
    tools_with_filters = [t for t in TOOLS if "filters" in t.inputSchema.get("properties", {})]
    for tool in tools_with_filters:
        assert tool.inputSchema["properties"]["filters"]["type"] == "object"


def test_ai_feature_tools_present():
    names = {t.name for t in TOOLS}
    assert {"get_ticket_full_context", "get_system_snapshot"}.issubset(names)


def test_analytics_cache_performance():
    assert analytics_reporting._cache_ttl <= 300
