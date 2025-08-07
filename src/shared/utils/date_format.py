"""
UTC-normalised minute-precision datetime helpers + SQLAlchemy type.

• DB format:  YYYY-MM-DD HH:MM   (16 characters)            ──▶ fits CHAR(16)
• All values stored naive/UTC; all values returned aware/UTC.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

DB_DATETIME_FORMAT = "%Y-%m-%d %H:%M"
_DB_STR_LEN = 16  # 'YYYY-MM-DD HH:MM'

# ─────────────────────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────────────────────
def format_db_datetime(dt: datetime) -> str:
    """
    Convert *dt* to a UTC, minute-precision string suitable for DB storage.
    Seconds and microseconds are truncated (not rounded).
    """
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    dt = dt.replace(second=0, microsecond=0)          # ≤ minute precision
    return dt.strftime(DB_DATETIME_FORMAT)


def parse_db_datetime(text: str) -> datetime:
    """
    Parse a DB datetime string (minute precision) **or** any ISO-8601 string
    and return an *aware* UTC datetime (seconds/micros zeroed).
    """
    try:
        # Python 3.11+ ISO-8601 parser (handles offsets, fractional seconds)
        dt = datetime.fromisoformat(text)
    except ValueError:
        dt = datetime.strptime(text, DB_DATETIME_FORMAT)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc).replace(second=0, microsecond=0)
    return dt

# ─────────────────────────────────────────────────────────────────────────────
# Optional SQLAlchemy integration
# ─────────────────────────────────────────────────────────────────────────────
try:
    from sqlalchemy.types import TypeDecorator, String
except ModuleNotFoundError:                          # pragma: no cover
    TypeDecorator = object                           # type: ignore
    String = object                                  # type: ignore


class FormattedDateTime(TypeDecorator):              # pyright: ignore[reportGeneralTypeIssues]
    """
    SQLAlchemy column type that stores minute-precision UTC strings (CHAR-16)
    and returns *aware* UTC `datetime` objects.
    """

    impl = String(_DB_STR_LEN)
    cache_ok = True

    # ────────────── outbound (Python → DB) ────────────────────────────────
    def process_bind_param(self, value: Any, dialect):  # type: ignore[override]
        if value is None:
            return None
        if isinstance(value, datetime):
            return format_db_datetime(value)
        if isinstance(value, str):
            # Accept ISO-8601 or already-formatted strings
            return (
                value if len(value) == _DB_STR_LEN
                else format_db_datetime(parse_db_datetime(value))
            )
        raise TypeError(f"Unsupported type for FormattedDateTime: {type(value)}")

    # ────────────── inbound (DB → Python) ─────────────────────────────────
    def process_result_value(self, value: Any, dialect):  # type: ignore[override]
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).replace(second=0, microsecond=0)
        if isinstance(value, str):
            return parse_db_datetime(value)
        raise TypeError(f"Unexpected DB value type: {type(value)}")
