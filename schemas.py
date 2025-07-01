from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class TicketBase(BaseModel):
    Subject: str
    Ticket_Body: str
    Ticket_Status_ID: Optional[int] = 1
    Ticket_Contact_Name: str
    Ticket_Contact_Email: EmailStr
    Asset_ID: Optional[int] = None
    Site_ID: Optional[int] = None
    Ticket_Category_ID: Optional[int] = None
    Assigned_Name: Optional[str] = None
    Assigned_Email: Optional[EmailStr] = None
    Severity_ID: Optional[int] = None
    Assigned_Vendor_ID: Optional[int] = None
    Resolution: Optional[str] = None

class TicketCreate(TicketBase):
    pass

class TicketOut(TicketBase):
    Ticket_ID: int
    Created_Date: Optional[datetime] = None

    class Config:
        orm_mode = True
