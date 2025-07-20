"""Deprecated - use :mod:`tools.user_services` instead."""

from __future__ import annotations

import warnings
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Sequence, Any, List

from db.models import OnCallShift

from .user_services import UserManager

_manager = UserManager()


async def get_current_oncall(db: AsyncSession) -> OnCallShift | None:
    warnings.warn(
        "get_current_oncall is deprecated; use UserManager.get_current_oncall",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.get_current_oncall(db)


async def list_oncall_schedule(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 10,
    filters: dict[str, Any] | None = None,
    sort: list[str] | None = None,
) -> Sequence[OnCallShift]:
    warnings.warn(
        "list_oncall_schedule is deprecated; use UserManager.list_oncall_schedule",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.list_oncall_schedule(db, skip=skip, limit=limit, filters=filters, sort=sort)
