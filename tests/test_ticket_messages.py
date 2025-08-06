import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.core.services.ticket_management import TicketManager
from src.infrastructure.database import SessionLocal
from src.shared.exceptions import DatabaseError


@pytest.mark.asyncio
async def test_post_message_db_error(monkeypatch):
    manager = TicketManager()
    async with SessionLocal() as db:
        async def fail_flush(*args, **kwargs):
            raise SQLAlchemyError("fail")

        async def dummy_rollback():
            pass

        monkeypatch.setattr(db, "flush", fail_flush)
        monkeypatch.setattr(db, "rollback", dummy_rollback)

        with pytest.raises(DatabaseError):

            await manager.post_message(db, 1, "oops", "u")


@pytest.mark.asyncio
async def test_post_message_defaults_sender_name():
    manager = TicketManager()
    async with SessionLocal() as db:
        msg = await manager.post_message(db, 1, "hello", "u")
        assert msg.SenderUserName == "u"
