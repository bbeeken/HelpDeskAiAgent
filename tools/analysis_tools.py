

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

import logging

from db.models import Ticket, TicketStatus, Site

logger = logging.getLogger(__name__)



async def tickets_by_status(db: AsyncSession) -> list[tuple[int | None, str | None, int]]:

    """
    Returns a list of tuples (status_id, status_label, count)
    for all tickets.
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
    return [(row[0], row[1], row[2]) for row in result.all()]



async def open_tickets_by_site(db: AsyncSession) -> list[tuple[int | None, str | None, int]]:

    """
    Returns list of tuples (site_id, site_label, open_count) for tickets
    not closed (status != 3).
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
    return [(row[0], row[1], row[2]) for row in result.all()]



async def sla_breaches(db: AsyncSession, sla_days: int = 2) -> int:

    """
    Count tickets older than sla_days and not closed.
    """
    from datetime import datetime, timedelta, UTC

    logger.info("Counting SLA breaches older than %s days", sla_days)
    cutoff = datetime.now(UTC) - timedelta(days=sla_days)
    result = await db.execute(
        select(func.count(Ticket.Ticket_ID))
        .filter(Ticket.Created_Date < cutoff)
        .filter(Ticket.Ticket_Status_ID != 3)
    )
    return result.scalar_one()



async def open_tickets_by_user(db: AsyncSession) -> list[tuple[str | None, int]]:

    """
    Returns list of tuples (assigned_email, open_count) for tickets not closed.
    """


    logger.info("Calculating open tickets by user")
    result = await db.execute(
        select(Ticket.Assigned_Email, func.count(Ticket.Ticket_ID))
        .filter(Ticket.Ticket_Status_ID != 3)
        .group_by(Ticket.Assigned_Email)
    )
    return [(row[0], row[1]) for row in result.all()]


async def tickets_waiting_on_user(db: AsyncSession) -> list[tuple[str | None, int]]:

    """
    Returns list of tuples (contact_email, waiting_count) for tickets awaiting contact reply (status == 4).
    """

    logger.info("Calculating tickets waiting on user")
    result = await db.execute(
        select(Ticket.Ticket_Contact_Email, func.count(Ticket.Ticket_ID))
        .filter(Ticket.Ticket_Status_ID == 4)
        .group_by(Ticket.Ticket_Contact_Email)
    )
    return [(row[0], row[1]) for row in result.all()]
