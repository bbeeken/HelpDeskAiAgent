from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class TicketIn(BaseModel):
    Subject: Optional[str] = None
    Ticket_Body: Optional[str] = None
    Ticket_Status_ID: Optional[int] = None
    Ticket_Contact_Name: Optional[str] = None
    Ticket_Contact_Email: Optional[str] = None
    Asset_ID: Optional[int] = None
    Site_ID: Optional[int] = None
    Ticket_Category_ID: Optional[int] = None
    Created_Date: Optional[datetime] = None
    Assigned_Name: Optional[str] = None
    Assigned_Email: Optional[str] = None
    Severity_ID: Optional[int] = None
    Assigned_Vendor_ID: Optional[int] = None
    Resolution: Optional[str] = None

class TicketOut(TicketIn):
    Ticket_ID: int

    class Config:
        orm_mode = True
