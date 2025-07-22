from pydantic import BaseModel
from typing import Optional
from datetime import date

class StatusCount(BaseModel):
    status_id: Optional[int]
    status_label: Optional[str]
    count: int

class SiteOpenCount(BaseModel):
    site_id: Optional[int]
    site_label: Optional[str]
    count: int


class UserOpenCount(BaseModel):
    """Open ticket count grouped by assigned technician."""

    assigned_email: Optional[str]
    count: int


class WaitingOnUserCount(BaseModel):
    """Count of tickets waiting on a contact reply."""

    contact_email: Optional[str]
    count: int


class TrendCount(BaseModel):
    """Ticket count grouped by creation date."""

    date: date
    count: int


class LateTicketDetail(BaseModel):
    """Detailed information about tickets that have breached the SLA."""

    ticket_id: int
    priority: Optional[int] = None
    age_days: int
    owner: Optional[str] = None
    status_id: Optional[int] = None
    sla_deadline: date

