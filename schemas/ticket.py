from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from typing import Annotated
from email_validator import validate_email, EmailNotValidError
from typing import Optional
from datetime import datetime


class TicketBase(BaseModel):
    Subject: Annotated[str, Field(max_length=255)]
    Ticket_Body: Annotated[str, Field()]
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
    Resolution: Optional[Annotated[str, Field()]] = None

    model_config = ConfigDict(str_max_length=None)

    @field_validator("Ticket_Contact_Email", "Assigned_Email", mode="before")
    def validate_emails(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and (v == "" or v.lower() == "null"):
            return None
        try:
            return validate_email(v, check_deliverability=False).normalized
        except EmailNotValidError as e:
            raise ValueError(str(e))


class TicketCreate(TicketBase):
    """Schema used when creating a new ticket."""

    model_config = ConfigDict(
        str_max_length=None,
        json_schema_extra={
            "example": {
                "Subject": "Printer not working",
                "Ticket_Body": "The office printer is jammed",
                "Ticket_Contact_Name": "Jane Doe",
                "Ticket_Contact_Email": "jane@example.com",
            }
        }
    )


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

    model_config = ConfigDict(extra="forbid", str_max_length=None)


class TicketIn(BaseModel):
    Subject: Optional[Annotated[str, Field(max_length=255)]] = None
    Ticket_Body: Optional[Annotated[str, Field()]] = None
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
    Resolution: Optional[Annotated[str, Field()]] = None

    @field_validator("Ticket_Contact_Email", "Assigned_Email", mode="before")
    def validate_emails(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and (v == "" or v.lower() == "null"):
            return None
        try:
            return validate_email(v, check_deliverability=False).normalized
        except EmailNotValidError as e:
            raise ValueError(str(e))

    model_config = ConfigDict(extra="forbid", str_max_length=None)


class TicketOut(TicketIn):
    Ticket_ID: int

    model_config = ConfigDict(
        str_max_length=None,
        from_attributes=True,
        json_schema_extra={
            "example": {
                "Ticket_ID": 1,
                "Subject": "Printer not working",
                "Ticket_Body": "The office printer is jammed",
                "Ticket_Status_ID": 1,
                "Ticket_Contact_Name": "Jane Doe",
                "Ticket_Contact_Email": "jane@example.com",
                "Created_Date": "2024-01-01T12:00:00Z",
            }
        },
    )



class TicketExpandedOut(TicketOut):

    """Ticket output schema that includes related labels."""

    status_label: Optional[str] = Field(None, alias="Ticket_Status_Label")
    Site_Label: Optional[str] = None
    Site_ID: Optional[int] = None
    Asset_Label: Optional[str] = None
    category_label: Optional[str] = Field(None, alias="Ticket_Category_Label")

    Assigned_Vendor_Name: Optional[str] = None
    Priority_Level: Optional[str] = None
    Closed_Date: Optional[datetime] = None
    LastModified: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, str_max_length=None)
