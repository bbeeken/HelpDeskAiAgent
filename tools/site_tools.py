from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import Site


async def get_site(db: AsyncSession, site_id: int):
    return await db.get(Site, site_id)


async def list_sites(db: AsyncSession, skip: int = 0, limit: int = 10):
    result = await db.execute(select(Site).offset(skip).limit(limit))
    return result.scalars().all()
