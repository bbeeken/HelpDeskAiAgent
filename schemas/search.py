from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from .search_params import TicketSearchParams


class TicketSearchOut(BaseModel):
    """Summary information returned by the search endpoint."""

    Ticket_ID: int
    Subject: str
    body_preview: str
    status_label: Optional[str] = None
    priority_level: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TicketSearchRequest(BaseModel):
    """Request body for the ticket search POST endpoint."""

    q: str = Field(..., min_length=1)
    limit: int = Field(10, ge=1, le=100)
    params: TicketSearchParams | None = None
