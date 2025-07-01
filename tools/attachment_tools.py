from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import TicketAttachment


async def get_ticket_attachments(db: AsyncSession, ticket_id: int):
    result = await db.execute(
        select(TicketAttachment).filter(TicketAttachment.Ticket_ID == ticket_id)
    )
    return result.scalars().all()
