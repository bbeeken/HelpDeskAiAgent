from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import Vendor


async def get_vendor(db: AsyncSession, vendor_id: int):
    return await db.get(Vendor, vendor_id)



async def list_vendors(db: AsyncSession, skip: int = 0, limit: int = 10):
    result = await db.execute(select(Vendor).offset(skip).limit(limit))
    return result.scalars().all()

