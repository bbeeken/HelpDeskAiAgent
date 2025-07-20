import pytest
from sqlalchemy.exc import SQLAlchemyError

from tools.ticket_management import TicketManager
from db.mssql import SessionLocal
from errors import DatabaseError


@pytest.mark.asyncio
async def test_post_message_db_error(monkeypatch):
    manager = TicketManager()
    async with SessionLocal() as db:
        async def fail_commit():
            raise SQLAlchemyError("fail")

        async def dummy_rollback():
            pass

        monkeypatch.setattr(db, "commit", fail_commit)
        monkeypatch.setattr(db, "rollback", dummy_rollback)

        with pytest.raises(DatabaseError):
            await manager.post_message(db, 1, "oops", "u")
