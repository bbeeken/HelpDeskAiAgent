from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


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
    """Schema used when creating a new ticket."""

    class Config:
        schema_extra = {
            "example": {
                "Subject": "Printer not working",
                "Ticket_Body": "The office printer is jammed",
                "Ticket_Contact_Name": "Jane Doe",
                "Ticket_Contact_Email": "jane@example.com",
            }
        }


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
        schema_extra = {
            "example": {
                "Ticket_ID": 1,
                "Subject": "Printer not working",
                "Ticket_Body": "The office printer is jammed",
                "Ticket_Status_ID": 1,
                "Ticket_Contact_Name": "Jane Doe",
                "Ticket_Contact_Email": "jane@example.com",
                "Created_Date": "2024-01-01T12:00:00Z",
            }
        }
