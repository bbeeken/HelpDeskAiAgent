"""Deprecated - use :mod:`tools.reference_data` instead."""

from __future__ import annotations

import warnings
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Asset
from typing import Any

from .reference_data import ReferenceDataManager

_manager = ReferenceDataManager()


async def get_asset(db: AsyncSession, asset_id: int) -> Asset | None:
    warnings.warn(
        "get_asset is deprecated; use ReferenceDataManager.get_asset",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.get_asset(db, asset_id)


async def list_assets(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 10,
    filters: dict[str, Any] | None = None,
    sort: list[str] | None = None,
) -> list[Asset]:
    warnings.warn(
        "list_assets is deprecated; use ReferenceDataManager.list_assets",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.list_assets(db, skip=skip, limit=limit, filters=filters, sort=sort)
