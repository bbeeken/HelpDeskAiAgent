from sqlalchemy.orm import Session
from sqlalchemy import func
from db.models import Ticket


class AnalyticsService:
    """Service providing reporting queries on ticket data."""

    def __init__(self, db: Session):
        self.db = db

    def tickets_by_status(self):
        results = (
            self.db.query(Ticket.Ticket_Status_ID, func.count(Ticket.Ticket_ID))
            .group_by(Ticket.Ticket_Status_ID)
            .all()
        )
        return [(row[0], row[1]) for row in results]

    def open_tickets_by_site(self):
        results = (
            self.db.query(Ticket.Site_ID, func.count(Ticket.Ticket_ID))
            .filter(Ticket.Ticket_Status_ID != 3)
            .group_by(Ticket.Site_ID)
            .all()
        )
        return [(row[0], row[1]) for row in results]

    def sla_breaches(self, sla_days: int = 2):
        from datetime import datetime, timedelta

        cutoff = datetime.utcnow() - timedelta(days=sla_days)
        return (
            self.db.query(func.count(Ticket.Ticket_ID))
            .filter(Ticket.Created_Date < cutoff)
            .filter(Ticket.Ticket_Status_ID != 3)
            .scalar()
        )

    def open_tickets_by_user(self):
        results = (
            self.db.query(Ticket.Assigned_Email, func.count(Ticket.Ticket_ID))
            .filter(Ticket.Ticket_Status_ID != 3)
            .group_by(Ticket.Assigned_Email)
            .all()
        )
        return [(row[0], row[1]) for row in results]

    def tickets_waiting_on_user(self):
        results = (
            self.db.query(Ticket.Ticket_Contact_Email, func.count(Ticket.Ticket_ID))
            .filter(Ticket.Ticket_Status_ID == 4)
            .group_by(Ticket.Ticket_Contact_Email)
            .all()
        )
        return [(row[0], row[1]) for row in results]
