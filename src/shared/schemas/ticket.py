from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, model_validator
from typing import Annotated, Optional, Any
from datetime import datetime, date


class TicketBase(BaseModel):
    Subject: Annotated[str, Field(max_length=255)]
    Ticket_Body: Annotated[str, Field()]
    Ticket_Status_ID: Optional[str] = "1"
    Ticket_Contact_Name: Annotated[str, Field(max_length=255)]
    Ticket_Contact_Email: EmailStr
    Asset_ID: Optional[str] = None
    Site_ID: Optional[int] = None
    Ticket_Category_ID: Optional[str] = None
    Assigned_Name: Optional[Annotated[str, Field(max_length=255)]] = None
    Assigned_Email: Optional[EmailStr] = None
    Severity_ID: Optional[int] = None
    Assigned_Vendor_ID: Optional[int] = None
    Most_Recent_Service_Scheduled_ID: Optional[str] = None
    Watchers: Optional[str] = None
    MetaData: Optional[str] = None
    HasServiceRequest: Optional[bool] = None
    Private: Optional[bool] = None
    EstimatedCompletionDate: Optional[date] = None
    CustomCompletionDate: Optional[date] = None
    ValidFrom: Optional[datetime] = None
    ValidTo: Optional[datetime] = None
    Resolution: Optional[Annotated[str, Field()]] = None

    @field_validator("Assigned_Email", mode="before")
    def _clean_assigned_email(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v


    @field_validator("HasServiceRequest", "Private", mode="before")
    def _parse_bit_bool(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v == "1":
                return True
            if v == "0":
                return False
            if v.upper() == "Y":
                return True
            if v.upper() == "N":
                return False
        return v

    @field_validator("EstimatedCompletionDate", "CustomCompletionDate", mode="before")
    def _coerce_date(cls, v: Any):
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            if "T" in v:
                v = v.split("T", 1)[0]
            if " " in v:
                v = v.split(" ", 1)[0]

        return v

    model_config = ConfigDict(str_max_length=None)


class TicketCreate(TicketBase):
    """Schema used when creating a new ticket."""

    LastModified: Optional[datetime] = None
    Version: Optional[int] = 1

    model_config = ConfigDict(
        str_max_length=None,
        json_schema_extra={
            "examples": [
                {
                    "Subject": "Printer not working",
                    "Ticket_Body": "The office printer is jammed and displays error code 34.",
                    "Ticket_Contact_Name": "Jane Doe",
                    "Ticket_Contact_Email": "jane@example.com",
                    "Asset_ID": "5",
                    "Site_ID": 2,
                    "Ticket_Category_ID": "1",
                },
                {
                    "Subject": "Website down",
                    "Ticket_Body": "The main website returns a 500 Internal Server Error.",
                    "Ticket_Contact_Name": "Alice Admin",
                    "Ticket_Contact_Email": "alice@example.com",
                    "Assigned_Name": "Bob Ops",
                    "Assigned_Email": "bob.ops@example.com",
                    "Ticket_Status_ID": "1",
                    "Site_ID": 3,
                    "Severity_ID": 3,
                },
            ]
        }
    )


class TicketUpdate(BaseModel):
    """Schema used when updating an existing ticket."""

    Subject: Optional[str] = None
    Ticket_Body: Optional[str] = None
    Ticket_Status_ID: Optional[str] = None
    Ticket_Contact_Name: Optional[str] = None
    Ticket_Contact_Email: Optional[EmailStr] = None
    Asset_ID: Optional[str] = None
    Site_ID: Optional[int] = None
    Ticket_Category_ID: Optional[str] = None
    Assigned_Name: Optional[str] = None
    Assigned_Email: Optional[EmailStr] = None
    Severity_ID: Optional[int] = None
    Assigned_Vendor_ID: Optional[int] = None
    Most_Recent_Service_Scheduled_ID: Optional[str] = None
    Watchers: Optional[str] = None
    MetaData: Optional[str] = None
    HasServiceRequest: Optional[bool] = None
    Private: Optional[bool] = None
    EstimatedCompletionDate: Optional[date] = None
    CustomCompletionDate: Optional[date] = None
    ValidFrom: Optional[datetime] = None
    ValidTo: Optional[datetime] = None
    Resolution: Optional[str] = None

    @model_validator(mode="after")
    def _ensure_fields_present(cls, values: "TicketUpdate") -> "TicketUpdate":
        if not values.model_fields_set:
            raise ValueError("At least one field must be supplied")
        return values

    @field_validator("HasServiceRequest", "Private", mode="before")
    def _parse_bit_bool(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v == "1":
                return True
            if v == "0":
                return False
            if v.upper() == "Y":
                return True
            if v.upper() == "N":
                return False
        return v

    model_config = ConfigDict(
        extra="forbid",
        str_max_length=None,
        json_schema_extra={
            "examples": [
                {"Subject": "Updated"},
                {"Assigned_Name": "Agent", "Ticket_Status_ID": "2"},
                {"Ticket_Status_ID": "3"},
            ]
        },
    )

    @field_validator("EstimatedCompletionDate", "CustomCompletionDate", mode="before")
    def _coerce_date(cls, v: Any):
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            if "T" in v:
                v = v.split("T", 1)[0]
            if " " in v:
                v = v.split(" ", 1)[0]
        return v


class TicketIn(TicketBase):
    Subject: Optional[Annotated[str, Field(max_length=255)]] = None
    Ticket_Body: Optional[Annotated[str, Field()]] = None
    Ticket_Status_ID: Optional[str] = None
    Ticket_Contact_Name: Optional[Annotated[str, Field(max_length=255)]] = None
    Ticket_Contact_Email: Optional[EmailStr] = None
    Asset_ID: Optional[str] = None
    Site_ID: Optional[int] = None
    Ticket_Category_ID: Optional[str] = None
    Created_Date: Optional[datetime] = None
    Assigned_Name: Optional[Annotated[str, Field(max_length=255)]] = None
    Assigned_Email: Optional[EmailStr] = None
    Severity_ID: Optional[int] = None
    Assigned_Vendor_ID: Optional[int] = None
    Most_Recent_Service_Scheduled_ID: Optional[str] = None
    Watchers: Optional[str] = None
    MetaData: Optional[str] = None
    EstimatedCompletionDate: Optional[date] = None
    CustomCompletionDate: Optional[date] = None
    ValidFrom: Optional[datetime] = None
    ValidTo: Optional[datetime] = None
    Resolution: Optional[Annotated[str, Field()]] = None
    Version: Optional[int] = None

    model_config = ConfigDict(extra="forbid", str_max_length=None)

    @field_validator("EstimatedCompletionDate", "CustomCompletionDate", mode="before")
    def _coerce_date(cls, v: Any):
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            if "T" in v:
                v = v.split("T", 1)[0]
            if " " in v:
                v = v.split(" ", 1)[0]
        return v


class TicketOut(TicketIn):
    Ticket_ID: int
    Version: int

    @field_validator("Ticket_Contact_Email", mode="before")
    def _clean_contact_email(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

    model_config = ConfigDict(
        str_max_length=None,
        from_attributes=True,
        json_schema_extra={
            "example": {
                "Ticket_ID": 1,
                "Subject": "Printer not working",
                "Ticket_Body": "The office printer is jammed",
                "Ticket_Status_ID": "1",
                "Ticket_Contact_Name": "Jane Doe",
                "Ticket_Contact_Email": "jane@example.com",
                "Created_Date": "2024-01-01T12:00:00Z",
            }
        },
    )


class TicketExpandedOut(TicketOut):

    """Ticket output schema that includes related labels."""

    status_label: Optional[str] = Field(None, alias="Ticket_Status_Label")
    site_label: Optional[str] = Field(None, alias="Site_Label")
    asset_label: Optional[str] = Field(None, alias="Asset_Label")
    category_label: Optional[str] = Field(None, alias="Ticket_Category_Label")
    vendor_name: Optional[str] = Field(None, alias="Assigned_Vendor_Name")
    priority_level: Optional[str] = Field(None, alias="Priority_Level")
    Most_Recent_Service_Scheduled_ID: Optional[str] = None
    Watchers: Optional[str] = None
    MetaData: Optional[str] = None
    ValidFrom: Optional[datetime] = None
    ValidTo: Optional[datetime] = None
    Site_ID: Optional[int] = None
    Closed_Date: Optional[datetime] = None
    LastModified: Optional[datetime] = None
    LastModfiedBy: Optional[str] = None
    Version: int

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
