from pydantic import BaseModel, ConfigDict
from typing import Optional


class TicketSearchOut(BaseModel):
    """Summary information returned by the search endpoint."""

    Ticket_ID: int
    Subject: str
    body_preview: str
    status_label: Optional[str] = None
    priority_level: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
