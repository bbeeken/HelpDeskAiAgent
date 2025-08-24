# UTC Datetime Format

All ticket timestamps must be stored as UTC strings with **millisecond** precision. The expected format is:

```
YYYY-MM-DD HH:MM:SS.mmm
```

This repository provides helpers to ensure datetimes are handled consistently:

- `format_db_datetime(dt)`: accepts a `datetime`, converts it to UTC, and returns a string trimmed to millisecond precision.
- `parse_search_datetime(value)`: parses a string or `datetime`, normalizing to UTC and truncating microseconds to milliseconds.
- `FormattedDateTime`: SQLAlchemy type that stores datetimes in the format above.

Fields like `Created_Date` and `LastModified` are populated by the database and should **never** be sent by clients.

## Filtering by creation date
```python
from datetime import datetime, timezone, timedelta
from src.shared.utils.date_format import format_db_datetime

params = {
    "created_after": format_db_datetime(datetime.now(timezone.utc) - timedelta(days=7)),
}
```

## Parsing search input
```python
from src.core.services.system_utilities import parse_search_datetime

dt = parse_search_datetime("2023-01-02 03:04:05.987654")
# dt.microsecond == 987000
```

## Common pitfalls
- Providing microseconds beyond three digits. Values such as `...05.987654` will be truncated to `...05.987` without rounding.
- Supplying non-UTC or naive datetimes. Always use timezone-aware UTC values like `datetime.now(timezone.utc)`.
