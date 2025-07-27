from datetime import datetime, UTC

from src.core.services.system_utilities import parse_search_datetime
from src.shared.utils.date_format import format_db_datetime


def test_parse_search_datetime_db_format():
    dt = datetime(2023, 1, 2, 3, 4, 5, 123456, tzinfo=UTC)
    text = format_db_datetime(dt)
    parsed = parse_search_datetime(text)


    assert parsed == dt


