from pydantic import BaseModel
from datetime import datetime


class AssetOut(BaseModel):
    ID: int
    Label: str

    class Config:
        orm_mode = True


class VendorOut(BaseModel):
    ID: int
    Name: str

    class Config:
        orm_mode = True


class SiteOut(BaseModel):
    ID: int
    Label: str

    class Config:
        orm_mode = True


class TicketCategoryOut(BaseModel):
    ID: int
    Label: str

    class Config:
        orm_mode = True


class TicketStatusOut(BaseModel):
    ID: int
    Label: str

    class Config:
        orm_mode = True


class TicketAttachmentOut(BaseModel):
    ID: int
    Ticket_ID: int
    Name: str
    WebURl: str
    UploadDateTime: datetime

    class Config:
        orm_mode = True


class TicketMessageOut(BaseModel):
    ID: int
    Ticket_ID: int
    Message: str
    SenderUserCode: str
    SenderUserName: str
    DateTimeStamp: datetime

    class Config:
        orm_mode = True
