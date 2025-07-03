from __future__ import annotations

from datetime import datetime, UTC
import logging
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import OnCallShift

logger = logging.getLogger(__name__)


async def get_current_oncall(db: AsyncSession) -> OnCallShift | None:
    """Return the on-call shift active at the current time."""
    now = datetime.now(UTC)
    result = await db.execute(
        select(OnCallShift)
        .where(OnCallShift.start_time <= now)
        .where(OnCallShift.end_time > now)
        .order_by(OnCallShift.start_time.desc())
        .limit(1)
    )
    shift = result.scalars().first()
    logger.info("Current on-call shift: %s", shift)
    return shift


async def list_oncall_schedule(db: AsyncSession, skip: int = 0, limit: int = 10) -> Sequence[OnCallShift]:
    """Return upcoming on-call shifts ordered by start_time."""
    result = await db.execute(
        select(OnCallShift).order_by(OnCallShift.start_time).offset(skip).limit(limit)
    )
    return result.scalars().all()
