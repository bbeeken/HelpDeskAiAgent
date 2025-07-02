from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Vendor

logger = logging.getLogger(__name__)


async def get_vendor(db: AsyncSession, vendor_id: int) -> Vendor | None:
    result = await db.execute(select(Vendor).where(Vendor.ID == vendor_id))
    return result.scalar_one_or_none()


async def list_vendors(db: AsyncSession, skip: int = 0, limit: int = 10) -> list[Vendor]:
    result = await db.execute(select(Vendor).offset(skip).limit(limit))
    return result.scalars().all()
