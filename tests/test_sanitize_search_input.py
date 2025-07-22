import pytest
from src.core.services.ticket_management import TicketManager


@pytest.mark.parametrize(
    "query,expected",
    [
        (" simple test ", "simple test"),
        ("DROP TABLE users; --", "DROP TABLE users --"),
        ("<<script>alert(1)</script>>", "scriptalert1script"),
        ("a" * 150, "a" * 100),
        ("", ""),
        ("   ", ""),
    ],
)
def test_sanitize_search_input(query, expected):
    manager = TicketManager()
    assert manager._sanitize_search_input(query) == expected
