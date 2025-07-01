from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Ticket(Base):
    __tablename__ = "Tickets_Master"
    Ticket_ID = Column(Integer, primary_key=True, index=True)
    Subject = Column(String)
    Ticket_Body = Column(Text)
    Ticket_Status_ID = Column(Integer)
    Ticket_Contact_Name = Column(String)
    Ticket_Contact_Email = Column(String)
    Asset_ID = Column(Integer)
    Site_ID = Column(Integer)
    Ticket_Category_ID = Column(Integer)
    Created_Date = Column(DateTime)
    Assigned_Name = Column(String)
    Assigned_Email = Column(String)
    Severity_ID = Column(Integer)
    Assigned_Vendor_ID = Column(Integer)
    Resolution = Column(Text)


class Asset(Base):
    __tablename__ = "Assets"
    ID = Column(Integer, primary_key=True, index=True)
    Label = Column(String)
    Asset_Category_ID = Column(Integer)
    Serial_Number = Column(String)
    Model = Column(String)
    Manufacturer = Column(String)
    Site_ID = Column(Integer)


class Vendor(Base):
    __tablename__ = "Vendors"
    ID = Column(Integer, primary_key=True, index=True)
    Name = Column(String)
    Site_ID = Column(Integer)
    Asset_Category_ID = Column(Integer)


class TicketAttachment(Base):
    __tablename__ = "Ticket_Attachments"
    ID = Column(Integer, primary_key=True, index=True)
    Ticket_ID = Column(Integer)
    Name = Column(String)
    WebURl = Column(String)
    UploadDateTime = Column(DateTime)


class TicketMessage(Base):
    __tablename__ = "Ticket_Messages"
    ID = Column(Integer, primary_key=True, index=True)
    Ticket_ID = Column(Integer)
    Message = Column(Text)
    SenderUserCode = Column(String)
    SenderUserName = Column(String)
    DateTimeStamp = Column(DateTime)


class Site(Base):
    __tablename__ = "Sites"
    ID = Column(Integer, primary_key=True, index=True)
    Label = Column(String)
    City = Column(String)
    State = Column(String)


class TicketCategory(Base):
    __tablename__ = "Ticket_Categories"
    ID = Column(Integer, primary_key=True, index=True)
    Label = Column(String)


class TicketStatus(Base):
    __tablename__ = "Ticket_Status"
    ID = Column(Integer, primary_key=True, index=True)
    Label = Column(String)
