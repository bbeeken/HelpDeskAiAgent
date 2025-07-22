import pytest
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError

from src.core.services.enhanced_context import EnhancedContextManager
from src.infrastructure.database import SessionLocal


@pytest.mark.asyncio
async def test_get_user_current_tickets_db_error(monkeypatch):
    async with SessionLocal() as db:
        manager = EnhancedContextManager(db)

        async def fail_execute(*args, **kwargs):
            raise SQLAlchemyError("fail")

        monkeypatch.setattr(db, "execute", fail_execute)
        result = await manager._get_user_current_tickets("u@example.com")
        assert result == []


@pytest.mark.asyncio
async def test_get_user_current_tickets_unexpected(monkeypatch):
    async with SessionLocal() as db:
        manager = EnhancedContextManager(db)

        async def boom(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(db, "execute", boom)
        with pytest.raises(RuntimeError):
            await manager._get_user_current_tickets("u@example.com")


def test_safe_datetime_diff_hours_invalid():
    assert (
        EnhancedContextManager._safe_datetime_diff_hours("bad", "bad") is None
    )


def test_safe_datetime_diff_hours_unexpected(monkeypatch):
    def boom(dt):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        EnhancedContextManager, "_ensure_timezone_aware", boom
    )

    with pytest.raises(RuntimeError):
        EnhancedContextManager._safe_datetime_diff_hours(
            datetime.now(timezone.utc), datetime.now(timezone.utc)
        )
