import pytest
from src.infrastructure.database import SessionLocal
from src.core.repositories.models import Ticket, TicketMessage, TicketAttachment
from src.core.services.advanced_query import AdvancedQueryManager
from src.shared.schemas.agent_data import AdvancedQuery


@pytest.mark.asyncio
async def test_batched_queries_match_single_queries():
    async with SessionLocal() as db:
        t1 = Ticket(
            Ticket_ID=1,
            Subject="T1",
            Ticket_Status_ID=1,
            Ticket_Contact_Name="Alice",
            Ticket_Contact_Email="alice@example.com",
        )
        t2 = Ticket(
            Ticket_ID=2,
            Subject="T2",
            Ticket_Status_ID=1,
            Ticket_Contact_Name="Bob",
            Ticket_Contact_Email="bob@example.com",
        )
        db.add_all([t1, t2])
        await db.commit()

        m1 = TicketMessage(
            Ticket_ID=1,
            Message="hello",
            SenderUserCode="alice",
            SenderUserName="Alice",
        )
        m2 = TicketMessage(
            Ticket_ID=2,
            Message="hi",
            SenderUserCode="bob",
            SenderUserName="Bob",
        )
        a1 = TicketAttachment(
            Ticket_ID=1,
            Name="file1",
            WebURl="url1",
            FileContent=b"d1",
        )
        a2 = TicketAttachment(
            Ticket_ID=2,
            Name="file2",
            WebURl="url2",
            FileContent=b"d2",
        )
        db.add_all([m1, m2, a1, a2])
        await db.commit()

        manager = AdvancedQueryManager(db)
        query = AdvancedQuery(
            include_messages=True,
            include_attachments=True,
            include_user_context=True,
        )
        result = await manager.query_tickets_advanced(query)

        for ticket in result.tickets:
            msgs = await manager.context_manager._get_ticket_messages(ticket["Ticket_ID"])
            atts = await manager.context_manager._get_ticket_attachments(ticket["Ticket_ID"])
            profile = await manager.context_manager.user_manager.get_user_by_email(
                ticket["Ticket_Contact_Email"]
            )
            assert ticket["messages"] == msgs
            assert ticket["attachments"] == atts
            assert ticket["user_profile"] == profile
