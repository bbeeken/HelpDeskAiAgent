from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import Asset


async def get_asset(db: AsyncSession, asset_id: int):
    return await db.get(Asset, asset_id)



async def list_assets(db: AsyncSession, skip: int = 0, limit: int = 10):
    result = await db.execute(select(Asset).offset(skip).limit(limit))
    return result.scalars().all()

