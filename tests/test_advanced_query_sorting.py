import pytest
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database import SessionLocal
from src.core.repositories.models import Ticket
from src.core.services.ticket_management import TicketManager
from src.core.services.advanced_query import AdvancedQueryManager
from src.shared.schemas.agent_data import AdvancedQuery


@pytest.mark.asyncio
async def test_multiple_sort_fields_honored(monkeypatch):
    async with SessionLocal() as db:
        t1 = Ticket(
            Subject="A",
            Ticket_Body="b",
            Ticket_Contact_Name="n",
            Ticket_Contact_Email="e@example.com",
            Created_Date=datetime(2023, 1, 1, tzinfo=UTC),
        )
        t2 = Ticket(
            Subject="B",
            Ticket_Body="b",
            Ticket_Contact_Name="n",
            Ticket_Contact_Email="e@example.com",
            Created_Date=datetime(2023, 1, 1, tzinfo=UTC),
        )
        tm = TicketManager()
        r1 = await tm.create_ticket(db, t1)
        r2 = await tm.create_ticket(db, t2)
        await db.commit()
        t1_id, t2_id = r1.data.Ticket_ID, r2.data.Ticket_ID

        executed = []
        orig_execute = AsyncSession.execute

        async def spy(self, statement, *args, **kwargs):
            executed.append(statement)
            return await orig_execute(self, statement, *args, **kwargs)

        monkeypatch.setattr(AsyncSession, "execute", spy)

        query = AdvancedQuery(
            sort_by=[
                {"field": "Created_Date", "direction": "asc"},
                {"field": "Ticket_ID", "direction": "desc"},
            ]
        )
        manager = AdvancedQueryManager(db)
        result = await manager.query_tickets_advanced(query)

        ids = [t["Ticket_ID"] for t in result.tickets]
        assert ids == [t2_id, t1_id]

        sql = str(executed[-1].compile(compile_kwargs={"literal_binds": True}))
        assert (
            'ORDER BY "V_Ticket_Master_Expanded"."Created_Date" ASC, '
            '"V_Ticket_Master_Expanded"."Ticket_ID" DESC' in sql
        )
