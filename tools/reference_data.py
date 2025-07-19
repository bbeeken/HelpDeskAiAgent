"""Unified reference data operations for lookup tables."""

from __future__ import annotations

import logging
from typing import Any, Sequence, Type

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Asset, Site, Vendor, TicketCategory, TicketStatus

logger = logging.getLogger(__name__)


class ReferenceDataManager:
    """Handles CRUD operations for reference data tables."""

    async def get_asset(self, db: AsyncSession, asset_id: int) -> Asset | None:
        return await db.get(Asset, asset_id)

    async def list_assets(
        self, db: AsyncSession, skip: int = 0, limit: int = 10
    ) -> list[Asset]:
        result = await db.execute(
            select(Asset).order_by(Asset.ID).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_site(self, db: AsyncSession, site_id: int) -> Site | None:
        return await db.get(Site, site_id)

    async def list_sites(
        self, db: AsyncSession, skip: int = 0, limit: int = 10
    ) -> list[Site]:
        result = await db.execute(
            select(Site).order_by(Site.ID).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_vendor(self, db: AsyncSession, vendor_id: int) -> Vendor | None:
        return await db.get(Vendor, vendor_id)

    async def list_vendors(
        self, db: AsyncSession, skip: int = 0, limit: int = 10
    ) -> list[Vendor]:
        result = await db.execute(
            select(Vendor).order_by(Vendor.ID).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def list_categories(self, db: AsyncSession) -> list[TicketCategory]:
        result = await db.execute(select(TicketCategory))
        return list(result.scalars().all())

    async def list_statuses(self, db: AsyncSession) -> list[TicketStatus]:
        result = await db.execute(select(TicketStatus))
        return list(result.scalars().all())

    async def get_by_id(
        self, db: AsyncSession, model_class: Type, entity_id: int
    ) -> Any | None:
        return await db.get(model_class, entity_id)

    async def list_all(
        self,
        db: AsyncSession,
        model_class: Type,
        skip: int = 0,
        limit: int = 10,
    ) -> Sequence:
        result = await db.execute(
            select(model_class).order_by(model_class.ID).offset(skip).limit(limit)
        )
        return result.scalars().all()

__all__ = ["ReferenceDataManager"]

