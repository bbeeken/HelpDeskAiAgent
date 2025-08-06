from sqlalchemy import Column, Integer, String, Text, Boolean
from src.shared.utils.date_format import FormattedDateTime
from sqlalchemy.orm import DeclarativeBase

# ``FormattedDateTime`` ensures datetime values are stored with millisecond
# precision and handles formatting transparently.


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
    Version = Column(Integer, default=1, nullable=False)

    Created_Date = Column(FormattedDateTime())
    Assigned_Name = Column(String)
    Assigned_Email = Column(String)
    Severity_ID = Column(Integer)
    Assigned_Vendor_ID = Column(Integer)


    Closed_Date = Column(FormattedDateTime())
    LastModified = Column(FormattedDateTime())
    LastModfiedBy = Column(String)
    Resolution = Column(Text)
    Most_Recent_Service_Scheduled_ID = Column(Integer, nullable=True)
    LastCreatedBy = Column(String, nullable=True)
    Watchers = Column(Text, nullable=True)
    EstimatedCompletionDate = Column(FormattedDateTime(), nullable=True)
    CustomCompletionDate = Column(FormattedDateTime(), nullable=True)
    EstimatedCompletionDateAsInt = Column(Integer, nullable=True)
    RV = Column(String, nullable=True)
    HasServiceRequest = Column(Boolean, nullable=True)
    Private = Column(Boolean, nullable=True)
    Collab_Emails = Column(String, nullable=True)
    OrderFormHTML = Column(Text, nullable=True)
    LastModifiedAsInt = Column(Integer, nullable=True)
    PM = Column(Boolean, nullable=True)
    Asset_ID_Mutiple = Column(String, nullable=True)
    MetaData = Column(Text, nullable=True)
    LastMetaDataUpdateDate = Column(FormattedDateTime(), nullable=True)
    ClosedBy = Column(String, nullable=True)
    ValidFrom = Column(FormattedDateTime(), nullable=True)
    ValidTo = Column(FormattedDateTime(), nullable=True)


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
    UploadDateTime = Column(FormattedDateTime())


class TicketMessage(Base):
    __tablename__ = "Ticket_Messages"
    ID = Column(Integer, primary_key=True, index=True)
    Ticket_ID = Column(Integer)
    Message = Column(Text)
    SenderUserCode = Column(String)
    SenderUserName = Column(String)

    DateTimeStamp = Column(FormattedDateTime())


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


class Priority(Base):
    __tablename__ = "Priority_Levels"
    ID = Column(Integer, primary_key=True, index=True)
    Level = Column(String)


class OnCallShift(Base):
    __tablename__ = "OnCall_Shifts"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, nullable=False, index=True)

    start_time = Column(FormattedDateTime(), nullable=False)
    end_time = Column(FormattedDateTime(), nullable=False)


class ViewBase(DeclarativeBase):
    """Declarative base for database views."""

    pass


class VTicketMasterExpanded(ViewBase):
    """Mapped class for the V_Ticket_Master_Expanded view."""

    __tablename__ = "V_Ticket_Master_Expanded"
    Ticket_ID = Column(Integer, primary_key=True, index=True)
    Subject = Column(String)
    Ticket_Body = Column(Text)
    Ticket_Status_ID = Column(Integer)
    Ticket_Status_Label = Column(String)
    Ticket_Contact_Name = Column(String)
    Ticket_Contact_Email = Column(String)
    Asset_ID = Column(Integer)
    Asset_Label = Column(String)
    Site_ID = Column(Integer)
    Site_Label = Column(String)
    Ticket_Category_ID = Column(Integer)
    Ticket_Category_Label = Column(String)
    Created_Date = Column(FormattedDateTime())
    Version = Column(Integer)
    Assigned_Name = Column(String)
    Assigned_Email = Column(String)
    Severity_ID = Column(Integer)
    Assigned_Vendor_ID = Column(Integer)
    Closed_Date = Column(FormattedDateTime())
    LastModified = Column(FormattedDateTime())

    LastModfiedBy = Column(String)

    Assigned_Vendor_Name = Column(String)
    Resolution = Column(Text)
    Priority_Level = Column(String)
