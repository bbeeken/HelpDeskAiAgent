"""Unified reference data operations for lookup tables."""

from __future__ import annotations

import logging
from typing import Any, Sequence, Type, List

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Asset, Site, Vendor, TicketCategory, TicketStatus

logger = logging.getLogger(__name__)


class ReferenceDataManager:
    """Handles CRUD operations for reference data tables."""

    async def get_asset(self, db: AsyncSession, asset_id: int) -> Asset | None:
        return await db.get(Asset, asset_id)

    async def list_assets(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        sort: list[str] | None = None,
    ) -> list[Asset]:
        query = select(Asset)
        if filters:
            conditions = []
            for key, value in filters.items():
                if hasattr(Asset, key):
                    attr = getattr(Asset, key)
                    conditions.append(attr.in_(value) if isinstance(value, list) else attr == value)
            if conditions:
                query = query.filter(and_(*conditions))
        if sort:
            if isinstance(sort, str):
                sort = [sort]
            order_cols = []
            for s in sort:
                direction = "asc"
                column = s
                if s.startswith("-"):
                    column = s[1:]
                    direction = "desc"
                elif " " in s:
                    column, dir_part = s.rsplit(" ", 1)
                    if dir_part.lower() in {"asc", "desc"}:
                        direction = dir_part.lower()
                if hasattr(Asset, column):
                    attr = getattr(Asset, column)
                    order_cols.append(attr.desc() if direction == "desc" else attr.asc())
            if order_cols:
                query = query.order_by(*order_cols)
        else:
            query = query.order_by(Asset.ID)
        if skip:
            query = query.offset(skip)
        if limit:
            query = query.limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_site(self, db: AsyncSession, site_id: int) -> Site | None:
        return await db.get(Site, site_id)

    async def list_sites(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        sort: list[str] | None = None,
    ) -> list[Site]:
        query = select(Site)
        if filters:
            conditions = []
            for key, value in filters.items():
                if hasattr(Site, key):
                    attr = getattr(Site, key)
                    conditions.append(attr.in_(value) if isinstance(value, list) else attr == value)
            if conditions:
                query = query.filter(and_(*conditions))
        if sort:
            if isinstance(sort, str):
                sort = [sort]
            order_cols = []
            for s in sort:
                direction = "asc"
                column = s
                if s.startswith("-"):
                    column = s[1:]
                    direction = "desc"
                elif " " in s:
                    column, dir_part = s.rsplit(" ", 1)
                    if dir_part.lower() in {"asc", "desc"}:
                        direction = dir_part.lower()
                if hasattr(Site, column):
                    attr = getattr(Site, column)
                    order_cols.append(attr.desc() if direction == "desc" else attr.asc())
            if order_cols:
                query = query.order_by(*order_cols)
        else:
            query = query.order_by(Site.ID)
        if skip:
            query = query.offset(skip)
        if limit:
            query = query.limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_vendor(self, db: AsyncSession, vendor_id: int) -> Vendor | None:
        return await db.get(Vendor, vendor_id)

    async def list_vendors(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        sort: list[str] | None = None,
    ) -> list[Vendor]:
        query = select(Vendor)
        if filters:
            conditions = []
            for key, value in filters.items():
                if hasattr(Vendor, key):
                    attr = getattr(Vendor, key)
                    conditions.append(attr.in_(value) if isinstance(value, list) else attr == value)
            if conditions:
                query = query.filter(and_(*conditions))
        if sort:
            if isinstance(sort, str):
                sort = [sort]
            order_cols = []
            for s in sort:
                direction = "asc"
                column = s
                if s.startswith("-"):
                    column = s[1:]
                    direction = "desc"
                elif " " in s:
                    column, dir_part = s.rsplit(" ", 1)
                    if dir_part.lower() in {"asc", "desc"}:
                        direction = dir_part.lower()
                if hasattr(Vendor, column):
                    attr = getattr(Vendor, column)
                    order_cols.append(attr.desc() if direction == "desc" else attr.asc())
            if order_cols:
                query = query.order_by(*order_cols)
        else:
            query = query.order_by(Vendor.ID)
        if skip:
            query = query.offset(skip)
        if limit:
            query = query.limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def list_categories(
        self,
        db: AsyncSession,
        filters: dict[str, Any] | None = None,
        sort: list[str] | None = None,
    ) -> list[TicketCategory]:
        query = select(TicketCategory)
        if filters:
            conditions = []
            for key, value in filters.items():
                if hasattr(TicketCategory, key):
                    attr = getattr(TicketCategory, key)
                    conditions.append(attr.in_(value) if isinstance(value, list) else attr == value)
            if conditions:
                query = query.filter(and_(*conditions))
        if sort:
            if isinstance(sort, str):
                sort = [sort]
            order_cols = []
            for s in sort:
                direction = "asc"
                column = s
                if s.startswith("-"):
                    column = s[1:]
                    direction = "desc"
                elif " " in s:
                    column, dir_part = s.rsplit(" ", 1)
                    if dir_part.lower() in {"asc", "desc"}:
                        direction = dir_part.lower()
                if hasattr(TicketCategory, column):
                    attr = getattr(TicketCategory, column)
                    order_cols.append(attr.desc() if direction == "desc" else attr.asc())
            if order_cols:
                query = query.order_by(*order_cols)
        else:
            query = query.order_by(TicketCategory.ID)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def list_statuses(
        self,
        db: AsyncSession,
        filters: dict[str, Any] | None = None,
        sort: list[str] | None = None,
    ) -> list[TicketStatus]:
        query = select(TicketStatus)
        if filters:
            conditions = []
            for key, value in filters.items():
                if hasattr(TicketStatus, key):
                    attr = getattr(TicketStatus, key)
                    conditions.append(attr.in_(value) if isinstance(value, list) else attr == value)
            if conditions:
                query = query.filter(and_(*conditions))
        if sort:
            if isinstance(sort, str):
                sort = [sort]
            order_cols = []
            for s in sort:
                direction = "asc"
                column = s
                if s.startswith("-"):
                    column = s[1:]
                    direction = "desc"
                elif " " in s:
                    column, dir_part = s.rsplit(" ", 1)
                    if dir_part.lower() in {"asc", "desc"}:
                        direction = dir_part.lower()
                if hasattr(TicketStatus, column):
                    attr = getattr(TicketStatus, column)
                    order_cols.append(attr.desc() if direction == "desc" else attr.asc())
            if order_cols:
                query = query.order_by(*order_cols)
        else:
            query = query.order_by(TicketStatus.ID)
        result = await db.execute(query)
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

