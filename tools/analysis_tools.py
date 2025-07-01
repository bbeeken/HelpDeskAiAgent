from sqlalchemy.orm import Session
from sqlalchemy import func
from db.models import Ticket

def tickets_by_status(db: Session):
    """
    Returns a list of tuples (status_id, count) for all tickets.
    """
    results = db.query(Ticket.Ticket_Status_ID, func.count(Ticket.Ticket_ID)) \
                .group_by(Ticket.Ticket_Status_ID).all()
    return [(row[0], row[1]) for row in results]

def open_tickets_by_site(db: Session):
    """
    Returns list of tuples (site_id, open_count) for tickets not closed (status != 3).
    """
    results = db.query(Ticket.Site_ID, func.count(Ticket.Ticket_ID)) \
                .filter(Ticket.Ticket_Status_ID != 3) \
                .group_by(Ticket.Site_ID).all()
    return [(row[0], row[1]) for row in results]

def sla_breaches(db: Session, sla_days: int = 2):
    """
    Count tickets older than sla_days and not closed.
    """
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=sla_days)
    return db.query(func.count(Ticket.Ticket_ID)) \
             .filter(Ticket.Created_Date < cutoff) \
             .filter(Ticket.Ticket_Status_ID != 3).scalar()

def open_tickets_by_user(db: Session):
    """
    Returns list of tuples (assigned_email, open_count) for tickets not closed.
    """
    results = db.query(Ticket.Assigned_Email, func.count(Ticket.Ticket_ID)) \
                .filter(Ticket.Ticket_Status_ID != 3) \
                .group_by(Ticket.Assigned_Email).all()
    return [(row[0], row[1]) for row in results]

def tickets_waiting_on_user(db: Session):
    """
    Returns list of tuples (contact_email, waiting_count) for tickets awaiting contact reply (status == 4).
    """
    results = db.query(Ticket.Ticket_Contact_Email, func.count(Ticket.Ticket_ID)) \
                .filter(Ticket.Ticket_Status_ID == 4) \
                .group_by(Ticket.Ticket_Contact_Email).all()
    return [(row[0], row[1]) for row in results]
