import pytest
from types import SimpleNamespace

from src.core.services.advanced_query import AdvancedQueryManager
from src.core.constants import DEFAULT_LABEL


@pytest.mark.asyncio
async def test_generate_query_aggregations_uses_default_label():
    manager = AdvancedQueryManager(db=None)
    ticket = SimpleNamespace(
        Ticket_Status_Label=None,
        Priority_Level=None,
        Site_Label=None,
        Ticket_Category_Label=None,
    )
    result = await manager._generate_query_aggregations([ticket])
    expected = {DEFAULT_LABEL: 1}
    assert result["status_breakdown"] == expected
    assert result["priority_breakdown"] == expected
    assert result["site_breakdown"] == expected
    assert result["category_breakdown"] == expected
