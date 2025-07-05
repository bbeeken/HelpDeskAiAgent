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
)

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
