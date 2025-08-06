from __future__ import annotations

from datetime import datetime, timezone

DB_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


def format_db_datetime(dt: datetime) -> str:
    """Return ``dt`` formatted for database storage."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    # Trim microseconds to milliseconds for consistent DB precision
    return dt.strftime(DB_DATETIME_FORMAT)[:-3]


def parse_db_datetime(text: str) -> datetime:
    """Parse a database datetime string into an aware ``datetime``."""
    try:
        base, frac = text.split(".")
    except ValueError:
        raise ValueError(f"Invalid datetime format: {text}")

    dt = datetime.strptime(base, "%Y-%m-%d %H:%M:%S")

    if len(frac) == 6:
        micro = int(frac)
    elif len(frac) == 3:
        micro = int(frac) * 1000
    else:
        raise ValueError(f"Invalid fractional second precision: {frac}")

    dt = dt.replace(microsecond=micro, tzinfo=timezone.utc)
    return dt


try:
    from sqlalchemy.types import TypeDecorator, String
except Exception:  # pragma: no cover - SQLAlchemy not available
    TypeDecorator = object
    String = object


class FormattedDateTime(TypeDecorator):
    """Store ``datetime`` values using :data:`DB_DATETIME_FORMAT`."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):  # type: ignore[override]
        if value is None:
            return value

        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str):
            text = value
            try:
                dt = parse_db_datetime(text)
            except ValueError:
                if text.endswith("Z"):
                    text = text[:-1] + "+00:00"
                dt = datetime.fromisoformat(text)
        else:
            raise TypeError(f"Unsupported type for FormattedDateTime: {type(value)}")

        return format_db_datetime(dt)

    def process_result_value(self, value, dialect):  # type: ignore[override]
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return parse_db_datetime(value)
        raise TypeError(f"Unexpected DB value type: {type(value)}")

