"""Deprecated - use :mod:`tools.reference_data` instead."""

from __future__ import annotations

import warnings
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Site

from .reference_data import ReferenceDataManager

_manager = ReferenceDataManager()


async def get_site(db: AsyncSession, site_id: int) -> Site | None:
    warnings.warn(
        "get_site is deprecated; use ReferenceDataManager.get_site",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.get_site(db, site_id)


async def list_sites(db: AsyncSession, skip: int = 0, limit: int = 10) -> list[Site]:
    warnings.warn(
        "list_sites is deprecated; use ReferenceDataManager.list_sites",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.list_sites(db, skip=skip, limit=limit)
