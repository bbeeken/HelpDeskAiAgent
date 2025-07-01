"""Wrappers around :class:`AnalyticsService` for backward compatibility."""

from sqlalchemy.orm import Session
from sqlalchemy import func
from db.models import Ticket
from services.analytics_service import AnalyticsService


def tickets_by_status(db: Session):
    """Return counts of tickets grouped by status."""
    return AnalyticsService(db).tickets_by_status()


def open_tickets_by_site(db: Session):
    return AnalyticsService(db).open_tickets_by_site()


def sla_breaches(db: Session, sla_days: int = 2):
    return AnalyticsService(db).sla_breaches(sla_days)


def open_tickets_by_user(db: Session):
    return AnalyticsService(db).open_tickets_by_user()

def tickets_waiting_on_user(db: Session):
    return AnalyticsService(db).tickets_waiting_on_user()



