
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from db.models import Vendor

logger = logging.getLogger(__name__)



async def get_vendor(db: AsyncSession, vendor_id: int) -> Vendor | None:
    return await db.get(Vendor, vendor_id)


async def list_vendors(db: AsyncSession, skip: int = 0, limit: int = 10) -> list[Vendor]:
    result = await db.execute(select(Vendor).offset(skip).limit(limit))
    return list(result.scalars().all())

