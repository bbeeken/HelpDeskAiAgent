from pydantic import BaseModel, EmailStr, constr, validator
from email_validator import validate_email, EmailNotValidError
from typing import Optional
from datetime import datetime


class TicketBase(BaseModel):
    Subject: constr(max_length=255)
    Ticket_Body: constr(max_length=2000)
    Ticket_Status_ID: Optional[int] = 1
    Ticket_Contact_Name: constr(max_length=255)
    Ticket_Contact_Email: EmailStr
    Asset_ID: Optional[int] = None
    Site_ID: Optional[int] = None
    Ticket_Category_ID: Optional[int] = None
    Assigned_Name: Optional[constr(max_length=255)] = None
    Assigned_Email: Optional[EmailStr] = None
    Severity_ID: Optional[int] = None
    Assigned_Vendor_ID: Optional[int] = None
    Resolution: Optional[constr(max_length=2000)] = None

    @validator("Ticket_Contact_Email", "Assigned_Email")
    def validate_emails(cls, v):
        if v is None:
            return v
        try:
            return validate_email(v, check_deliverability=False).email
        except EmailNotValidError as e:
            raise ValueError(str(e))


class TicketCreate(TicketBase):
    """Schema used when creating a new ticket."""

    pass


class TicketIn(BaseModel):
    Subject: Optional[constr(max_length=255)] = None
    Ticket_Body: Optional[constr(max_length=2000)] = None
    Ticket_Status_ID: Optional[int] = None
    Ticket_Contact_Name: Optional[constr(max_length=255)] = None
    Ticket_Contact_Email: Optional[EmailStr] = None
    Asset_ID: Optional[int] = None
    Site_ID: Optional[int] = None
    Ticket_Category_ID: Optional[int] = None
    Created_Date: Optional[datetime] = None
    Assigned_Name: Optional[constr(max_length=255)] = None
    Assigned_Email: Optional[EmailStr] = None
    Severity_ID: Optional[int] = None
    Assigned_Vendor_ID: Optional[int] = None
    Resolution: Optional[constr(max_length=2000)] = None

    @validator("Ticket_Contact_Email", "Assigned_Email")
    def validate_emails(cls, v):
        if v is None:
            return v
        try:
            return validate_email(v, check_deliverability=False).email
        except EmailNotValidError as e:
            raise ValueError(str(e))


class TicketOut(TicketIn):
    Ticket_ID: int

    class Config:
        orm_mode = True
