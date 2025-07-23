import html
import pytest
from src.core.services.ticket_management import TicketManager


@pytest.mark.parametrize(
    "query",
    [
        " simple test ",
        "DROP TABLE users; --",
        "<<script>alert(1)</script>>",
        "a" * 150,
        "",
        "   ",
    ],
)
def test_sanitize_search_input(query):
    manager = TicketManager()
    expected = html.escape(query).strip()
    assert manager._sanitize_search_input(query) == expected
