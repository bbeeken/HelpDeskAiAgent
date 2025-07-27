from __future__ import annotations

from datetime import datetime, timezone

DB_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


def format_db_datetime(dt: datetime) -> str:
    """Return ``dt`` formatted for database storage."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime(DB_DATETIME_FORMAT)


def parse_db_datetime(text: str) -> datetime:
    """Parse a database datetime string into an aware ``datetime``."""
    dt = datetime.strptime(text, DB_DATETIME_FORMAT)
    return dt.replace(tzinfo=timezone.utc)


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
            return format_db_datetime(value)
        if isinstance(value, str):
            return value
        raise TypeError(f"Unsupported type for FormattedDateTime: {type(value)}")

    def process_result_value(self, value, dialect):  # type: ignore[override]
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return parse_db_datetime(value)
        raise TypeError(f"Unexpected DB value type: {type(value)}")

