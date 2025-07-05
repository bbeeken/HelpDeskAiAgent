"""Analytics helpers for summarizing ticket data."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from typing import Any

import logging

from db.models import Ticket, TicketStatus, Site
from schemas.analytics import (
    StatusCount,
    SiteOpenCount,
    UserOpenCount,
    WaitingOnUserCount,
    TrendAnalysis,
)
from dataclasses import asdict
from datetime import datetime, timedelta, UTC

logger = logging.getLogger(__name__)



async def tickets_by_status(db: AsyncSession) -> list[StatusCount]:
    """Return counts of tickets grouped by status.

    Each :class:`StatusCount` contains ``status_id``, ``status_label`` and
    ``count`` fields.
    """


    logger.info("Calculating tickets by status")
    result = await db.execute(
        select(
            Ticket.Ticket_Status_ID,
            TicketStatus.Label,
            func.count(Ticket.Ticket_ID),
        )
        .join(TicketStatus, Ticket.Ticket_Status_ID == TicketStatus.ID, isouter=True)
        .group_by(Ticket.Ticket_Status_ID, TicketStatus.Label)
    )
    return [
        StatusCount(status_id=row[0], status_label=row[1], count=row[2])
        for row in result.all()
    ]



async def open_tickets_by_site(db: AsyncSession) -> list[SiteOpenCount]:
    """Return open ticket counts grouped by site.

    Each :class:`SiteOpenCount` contains ``site_id``, ``site_label`` and
    ``count`` fields for tickets not closed (status != 3).
    """


    logger.info("Calculating open tickets by site")
    result = await db.execute(
        select(
            Ticket.Site_ID,
            Site.Label,
            func.count(Ticket.Ticket_ID),
        )
        .join(Site, Ticket.Site_ID == Site.ID, isouter=True)
        .filter(Ticket.Ticket_Status_ID != 3)
        .group_by(Ticket.Site_ID, Site.Label)
    )
    return [
        SiteOpenCount(site_id=row[0], site_label=row[1], count=row[2])
        for row in result.all()
    ]



async def sla_breaches(
    db: AsyncSession,
    sla_days: int = 2,
    filters: dict[str, Any] | None = None,
    status_ids: list[int] | None = None,
) -> int:

    """Count tickets older than ``sla_days`` with optional filtering."""
    from datetime import datetime, timedelta, UTC

    logger.info(
        "Counting SLA breaches older than %s days with filters=%s statuses=%s",
        sla_days,
        filters,
        status_ids,
    )
    cutoff = datetime.now(UTC) - timedelta(days=sla_days)

    query = select(func.count(Ticket.Ticket_ID)).filter(Ticket.Created_Date < cutoff)

    if status_ids is not None:
        query = query.filter(Ticket.Ticket_Status_ID.in_(status_ids))
    else:
        query = query.filter(Ticket.Ticket_Status_ID != 3)

    if filters:
        for key, value in filters.items():
            if hasattr(Ticket, key):
                query = query.filter(getattr(Ticket, key) == value)

    result = await db.execute(query)
    return result.scalar_one()



async def open_tickets_by_user(db: AsyncSession) -> list[UserOpenCount]:
    """Return open ticket counts grouped by assigned technician.

    Each :class:`UserOpenCount` contains ``assigned_email`` and ``count``
    fields for tickets not closed.
    """


    logger.info("Calculating open tickets by user")
    result = await db.execute(
        select(Ticket.Assigned_Email, func.count(Ticket.Ticket_ID))
        .filter(Ticket.Ticket_Status_ID != 3)
        .group_by(Ticket.Assigned_Email)
    )
    return [
        UserOpenCount(assigned_email=row[0], count=row[1])
        for row in result.all()
    ]


async def tickets_waiting_on_user(db: AsyncSession) -> list[WaitingOnUserCount]:
    """Return counts of tickets awaiting a user response.

    Each :class:`WaitingOnUserCount` contains ``contact_email`` and ``count``
    fields for tickets where status is ``4``.
    """

    logger.info("Calculating tickets waiting on user")
    result = await db.execute(
        select(Ticket.Ticket_Contact_Email, func.count(Ticket.Ticket_ID))
        .filter(Ticket.Ticket_Status_ID == 4)
        .group_by(Ticket.Ticket_Contact_Email)
    )
    return [
        WaitingOnUserCount(contact_email=row[0], count=row[1])
        for row in result.all()
    ]


async def ticket_volume_trend(
    db: AsyncSession, days: int = 7, now: datetime | None = None
) -> TrendAnalysis:
    """Compute percent change in ticket creation volume."""

    if now is None:
        now = datetime.now(UTC)

    current_start = now - timedelta(days=days)
    previous_start = now - timedelta(days=2 * days)

    current_query = select(func.count(Ticket.Ticket_ID)).filter(
        Ticket.Created_Date >= current_start
    )
    previous_query = (
        select(func.count(Ticket.Ticket_ID))
        .filter(Ticket.Created_Date >= previous_start)
        .filter(Ticket.Created_Date < current_start)
    )

    current_count = await db.scalar(current_query) or 0
    previous_count = await db.scalar(previous_query) or 0

    if previous_count:
        pct = ((current_count - previous_count) / previous_count) * 100
    elif current_count:
        pct = 100.0
    else:
        pct = 0.0

    if current_count > previous_count:
        direction = "up"
    elif current_count < previous_count:
        direction = "down"
    else:
        direction = "flat"

    return TrendAnalysis(direction=direction, percent_change=pct, confidence=1.0)


async def resolution_time_trend(
    db: AsyncSession, days: int = 7, now: datetime | None = None
) -> TrendAnalysis:
    """Compare average resolution time for closed tickets."""

    if now is None:
        now = datetime.now(UTC)

    current_start = now - timedelta(days=days)
    previous_start = now - timedelta(days=2 * days)

    async def _average(start: datetime, end: datetime | None) -> float:
        query = select(Ticket.Created_Date).filter(Ticket.Ticket_Status_ID == 3)
        query = query.filter(Ticket.Created_Date >= start)
        if end is not None:
            query = query.filter(Ticket.Created_Date < end)
        rows = (await db.execute(query)).scalars().all()
        if not rows:
            return 0.0
        durations = []
        for d in rows:
            if d.tzinfo is None:
                d = d.replace(tzinfo=UTC)
            durations.append((now - d).total_seconds())
        return sum(durations) / len(durations)

    current_avg = await _average(current_start, None)
    previous_avg = await _average(previous_start, current_start)

    if previous_avg:
        pct = ((current_avg - previous_avg) / previous_avg) * 100
    elif current_avg:
        pct = 100.0
    else:
        pct = 0.0

    if current_avg > previous_avg:
        direction = "up"
    elif current_avg < previous_avg:
        direction = "down"
    else:
        direction = "flat"

    return TrendAnalysis(direction=direction, percent_change=pct, confidence=1.0)
