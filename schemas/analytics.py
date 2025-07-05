from pydantic import BaseModel
from typing import Optional
from dataclasses import dataclass

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


@dataclass
class TrendAnalysis:
    """Simple trend description for analytics graphs."""

    direction: str
    percent_change: float
    confidence: float
