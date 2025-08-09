from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TicketSearchParams(BaseModel):
    """Optional search parameters for filtering tickets."""

    Ticket_ID: Optional[int] = None
    Subject: Optional[str] = None
    Ticket_Body: Optional[str] = None
    Ticket_Status_ID: Optional[str] = None
    Ticket_Status_Label: Optional[str] = None
    Ticket_Contact_Name: Optional[str] = None
    Ticket_Contact_Email: Optional[str] = None
    Asset_ID: Optional[str] = None
    Asset_Label: Optional[str] = None
    Site_ID: Optional[int] = None
    Site_Label: Optional[str] = None
    Ticket_Category_ID: Optional[str] = None
    Ticket_Category_Label: Optional[str] = None
    Created_Date: Optional[datetime] = None
    Assigned_Name: Optional[str] = None
    Assigned_Email: Optional[str] = None
    Severity_ID: Optional[int] = None
    Assigned_Vendor_ID: Optional[int] = None
    Assigned_Vendor_Name: Optional[str] = None
    Resolution: Optional[str] = None
    Priority_Level: Optional[str] = None

    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None

    sort: Optional[str] = Field(
        default=None,
        description="Order by Created_Date",
        pattern="^(oldest|newest)$",
    )

    model_config = ConfigDict(extra="forbid")
