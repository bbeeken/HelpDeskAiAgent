from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import TicketCategory


async def list_categories(db: AsyncSession):
    result = await db.execute(select(TicketCategory))
    return result.scalars().all()
