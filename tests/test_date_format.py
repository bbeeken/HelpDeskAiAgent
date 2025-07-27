from datetime import datetime, UTC

from src.core.services.system_utilities import parse_search_datetime
from src.shared.utils.date_format import format_db_datetime


def test_parse_search_datetime_db_format():
    dt = datetime(2023, 1, 2, 3, 4, 5, 123456, tzinfo=UTC)
    text = format_db_datetime(dt)
    parsed = parse_search_datetime(text)

    assert parsed == dt.replace(microsecond=123000)


def test_parse_search_datetime_datetime_input():
    dt = datetime(2024, 2, 3, 4, 5, 6, 987654, tzinfo=UTC)
    parsed = parse_search_datetime(dt)
    assert parsed.microsecond == 987000

