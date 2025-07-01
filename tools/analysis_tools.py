from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from db.models import Ticket


async def tickets_by_status(db: AsyncSession):
    """
    Returns a list of tuples (status_id, count) for all tickets.
    """

    result = await db.execute(
        select(Ticket.Ticket_Status_ID, func.count(Ticket.Ticket_ID)).group_by(
            Ticket.Ticket_Status_ID
        )
    )
    return [(row[0], row[1]) for row in result.all()]


async def open_tickets_by_site(db: AsyncSession):
    """
    Returns list of tuples (site_id, open_count) for tickets not closed (status != 3).
    """

    result = await db.execute(
        select(Ticket.Site_ID, func.count(Ticket.Ticket_ID))
        .filter(Ticket.Ticket_Status_ID != 3)
        .group_by(Ticket.Site_ID)
    )
    return [(row[0], row[1]) for row in result.all()]


async def sla_breaches(db: AsyncSession, sla_days: int = 2):
    """
    Count tickets older than sla_days and not closed.
    """
    from datetime import datetime, timedelta

    cutoff = datetime.utcnow() - timedelta(days=sla_days)
    result = await db.execute(
        select(func.count(Ticket.Ticket_ID))
        .filter(Ticket.Created_Date < cutoff)
        .filter(Ticket.Ticket_Status_ID != 3)
    )
    return result.scalar()


async def open_tickets_by_user(db: AsyncSession):
    """
    Returns list of tuples (assigned_email, open_count) for tickets not closed.
    """

    result = await db.execute(
        select(Ticket.Assigned_Email, func.count(Ticket.Ticket_ID))
        .filter(Ticket.Ticket_Status_ID != 3)
        .group_by(Ticket.Assigned_Email)
    )
    return [(row[0], row[1]) for row in result.all()]

async def tickets_waiting_on_user(db: AsyncSession):
    """
    Returns list of tuples (contact_email, waiting_count) for tickets awaiting contact reply (status == 4).
    """
    result = await db.execute(
        select(Ticket.Ticket_Contact_Email, func.count(Ticket.Ticket_ID))
        .filter(Ticket.Ticket_Status_ID == 4)
        .group_by(Ticket.Ticket_Contact_Email)
    )
    return [(row[0], row[1]) for row in result.all()]



