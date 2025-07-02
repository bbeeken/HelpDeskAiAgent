
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

from db.models import Ticket

logger = logging.getLogger(__name__)



def tickets_by_status(db: Session) -> list[tuple[int | None, int]]:

    """
    Returns a list of tuples (status_id, count) for all tickets.
    """


    logger.info("Calculating tickets by status")
    results = db.query(Ticket.Ticket_Status_ID, func.count(Ticket.Ticket_ID)) \
                .group_by(Ticket.Ticket_Status_ID).all()
    return [(row[0], row[1]) for row in results]



def open_tickets_by_site(db: Session) -> list[tuple[int | None, int]]:

    """
    Returns list of tuples (site_id, open_count) for tickets not closed (status != 3).
    """


    logger.info("Calculating open tickets by site")
    results = db.query(Ticket.Site_ID, func.count(Ticket.Ticket_ID)) \
                .filter(Ticket.Ticket_Status_ID != 3) \
                .group_by(Ticket.Site_ID).all()
    return [(row[0], row[1]) for row in results]



def sla_breaches(db: Session, sla_days: int = 2) -> int:

    """
    Count tickets older than sla_days and not closed.
    """
    from datetime import datetime, timedelta

    logger.info("Counting SLA breaches older than %s days", sla_days)
    cutoff = datetime.utcnow() - timedelta(days=sla_days)
    result = await db.execute(
        select(func.count(Ticket.Ticket_ID))
        .filter(Ticket.Created_Date < cutoff)
        .filter(Ticket.Ticket_Status_ID != 3)
    )
    return result.scalar()



def open_tickets_by_user(db: Session) -> list[tuple[str | None, int]]:

    """
    Returns list of tuples (assigned_email, open_count) for tickets not closed.
    """


    logger.info("Calculating open tickets by user")
    results = db.query(Ticket.Assigned_Email, func.count(Ticket.Ticket_ID)) \
                .filter(Ticket.Ticket_Status_ID != 3) \
                .group_by(Ticket.Assigned_Email).all()
    return [(row[0], row[1]) for row in results]


def tickets_waiting_on_user(db: Session) -> list[tuple[str | None, int]]:

    """
    Returns list of tuples (contact_email, waiting_count) for tickets awaiting contact reply (status == 4).
    """

    logger.info("Calculating tickets waiting on user")
    results = db.query(Ticket.Ticket_Contact_Email, func.count(Ticket.Ticket_ID)) \
                .filter(Ticket.Ticket_Status_ID == 4) \
                .group_by(Ticket.Ticket_Contact_Email).all()
    return [(row[0], row[1]) for row in results]





