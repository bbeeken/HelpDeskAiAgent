from pydantic import BaseModel, EmailStr, Field, validator
from typing import Annotated
from email_validator import validate_email, EmailNotValidError
from typing import Optional
from datetime import datetime


class TicketBase(BaseModel):
    Subject: Annotated[str, Field(max_length=255)]
    Ticket_Body: Annotated[str, Field(max_length=2000)]
    Ticket_Status_ID: Optional[int] = 1
    Ticket_Contact_Name: Annotated[str, Field(max_length=255)]
    Ticket_Contact_Email: EmailStr
    Asset_ID: Optional[int] = None
    Site_ID: Optional[int] = None
    Ticket_Category_ID: Optional[int] = None
    Assigned_Name: Optional[Annotated[str, Field(max_length=255)]] = None
    Assigned_Email: Optional[EmailStr] = None
    Priority_ID: Optional[int] = None
    Assigned_Vendor_ID: Optional[int] = None
    Resolution: Optional[Annotated[str, Field(max_length=2000)]] = None

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

    class Config:
        schema_extra = {
            "example": {
                "Subject": "Printer not working",
                "Ticket_Body": "The office printer is jammed",
                "Ticket_Contact_Name": "Jane Doe",
                "Ticket_Contact_Email": "jane@example.com",
            }
        }


class TicketUpdate(BaseModel):
    """Schema used when updating an existing ticket."""

    Subject: Optional[str] = None
    Ticket_Body: Optional[str] = None
    Ticket_Status_ID: Optional[int] = None
    Ticket_Contact_Name: Optional[str] = None
    Ticket_Contact_Email: Optional[EmailStr] = None
    Asset_ID: Optional[int] = None
    Site_ID: Optional[int] = None
    Ticket_Category_ID: Optional[int] = None
    Assigned_Name: Optional[str] = None
    Assigned_Email: Optional[EmailStr] = None
    Priority_ID: Optional[int] = None
    Assigned_Vendor_ID: Optional[int] = None
    Resolution: Optional[str] = None

    class Config:
        extra = "forbid"


class TicketIn(BaseModel):
    Subject: Optional[Annotated[str, Field(max_length=255)]] = None
    Ticket_Body: Optional[Annotated[str, Field(max_length=2000)]] = None
    Ticket_Status_ID: Optional[int] = None
    Ticket_Contact_Name: Optional[Annotated[str, Field(max_length=255)]] = None
    Ticket_Contact_Email: Optional[EmailStr] = None
    Asset_ID: Optional[int] = None
    Site_ID: Optional[int] = None
    Ticket_Category_ID: Optional[int] = None
    Created_Date: Optional[datetime] = None
    Assigned_Name: Optional[Annotated[str, Field(max_length=255)]] = None
    Assigned_Email: Optional[EmailStr] = None
    Priority_ID: Optional[int] = None
    Assigned_Vendor_ID: Optional[int] = None
    Resolution: Optional[Annotated[str, Field(max_length=2000)]] = None

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



class TicketExpandedOut(TicketOut):

    """Ticket output schema that includes related labels."""


    Ticket_Status_Label: Optional[str] = None
    Status_Label: Optional[str] = None
    Site_Label: Optional[str] = None
    Site_ID: Optional[int] = None
    Asset_Label: Optional[str] = None
    Ticket_Category_Label: Optional[str] = None
    Category_Label: Optional[str] = None

    Assigned_Vendor_Name: Optional[str] = None
    Priority_Level: Optional[str] = None

    @property
    def Status_Label(self) -> Optional[str]:
        return self.Ticket_Status_Label

    @property
    def Category_Label(self) -> Optional[str]:
        return self.Ticket_Category_Label


    class Config:
        orm_mode = True
