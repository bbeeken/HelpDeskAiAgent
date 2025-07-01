from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import TicketStatus


async def list_statuses(db: AsyncSession):
    result = await db.execute(select(TicketStatus))
    return result.scalars().all()
