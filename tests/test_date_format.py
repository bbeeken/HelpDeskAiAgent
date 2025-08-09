from datetime import datetime, date, UTC

from src.core.services.system_utilities import parse_search_datetime
from src.shared.utils.date_format import (
    format_db_datetime,
    FormattedDateTime,
    normalize_to_utc_minute,
)


def test_parse_search_datetime_db_format():
    dt = datetime(2023, 1, 2, 3, 4, 5, 123456, tzinfo=UTC)
    text = format_db_datetime(dt)
    parsed = parse_search_datetime(text)

    expected = dt.replace(microsecond=(dt.microsecond // 1000) * 1000)

    assert parsed == expected


def test_formatted_datetime_truncates_datetime_input():
    typ = FormattedDateTime()
    dt = datetime(2023, 1, 2, 3, 4, 5, 987654, tzinfo=UTC)
    assert typ.process_bind_param(dt, None) == "2023-01-02 03:04:05.987"


def test_formatted_datetime_truncates_string_input():
    typ = FormattedDateTime()
    text = "2023-01-02 03:04:05.987654"
    assert typ.process_bind_param(text, None) == "2023-01-02 03:04:05.987"


def test_parse_search_datetime_trims_microseconds():
    text = "2025-08-06 02:20:22.485621"
    dt = parse_search_datetime(text)
    assert format_db_datetime(dt) == "2025-08-06 02:20:22.485"


def test_normalize_to_utc_minute_handles_date():
    d = date(2024, 5, 7)
    dt = normalize_to_utc_minute(d)
    assert dt == datetime(2024, 5, 7, tzinfo=UTC)


def test_formatted_datetime_binds_date_midnight():
    typ = FormattedDateTime()
    d = date(2024, 5, 7)
    assert typ.process_bind_param(d, None) == "2024-05-07 00:00:00.000"
