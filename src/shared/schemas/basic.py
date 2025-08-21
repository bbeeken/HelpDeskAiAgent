from pydantic import BaseModel, ConfigDict
from datetime import datetime


class AssetOut(BaseModel):
    ID: int
    Label: str

    model_config = ConfigDict(from_attributes=True)


class VendorOut(BaseModel):
    ID: int
    Name: str

    model_config = ConfigDict(from_attributes=True)


class SiteOut(BaseModel):
    ID: int
    Label: str

    model_config = ConfigDict(from_attributes=True)


class TicketCategoryOut(BaseModel):
    ID: int
    Label: str

    model_config = ConfigDict(from_attributes=True)


class TicketStatusOut(BaseModel):
    ID: int
    Label: str

    model_config = ConfigDict(from_attributes=True)


class TicketAttachmentOut(BaseModel):
    ID: int
    Ticket_ID: int
    Name: str
    WebURl: str
    UploadDateTime: datetime
    FileContent: bytes
    Binary: bytes | None = None
    ContentBytes: bytes | None = None

    model_config = ConfigDict(from_attributes=True)


class TicketMessageOut(BaseModel):
    ID: int
    Ticket_ID: int
    Message: str
    SenderUserCode: str
    SenderUserName: str
    DateTimeStamp: datetime

    model_config = ConfigDict(from_attributes=True)
