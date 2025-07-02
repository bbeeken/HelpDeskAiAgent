
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from db.models import Vendor

logger = logging.getLogger(__name__)



async def get_vendor(db: AsyncSession, vendor_id: int) -> Vendor | None:
    result = await db.execute(select(Vendor).filter(Vendor.ID == vendor_id))
    return result.scalars().first()


async def list_vendors(db: AsyncSession, skip: int = 0, limit: int = 10) -> list[Vendor]:
    result = await db.execute(select(Vendor).offset(skip).limit(limit))
    return result.scalars().all()

