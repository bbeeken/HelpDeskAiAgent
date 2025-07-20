import pytest
from pydantic import ValidationError
from src.shared.schemas.ticket import TicketCreate


def test_invalid_email():
    with pytest.raises(ValidationError):
        TicketCreate(
            Subject="Test",
            Ticket_Body="Body",
            Ticket_Contact_Name="Name",
            Ticket_Contact_Email="notanemail",
        )


def test_subject_too_long():
    with pytest.raises(ValidationError):
        TicketCreate(
            Subject="x" * 256,
            Ticket_Body="Body",
            Ticket_Contact_Name="Name",
            Ticket_Contact_Email="test@example.com",
        )


def test_long_body_allowed():
    long_text = "x" * 3000
    obj = TicketCreate(
        Subject="Test",
        Ticket_Body=long_text,
        Ticket_Contact_Name="Name",
        Ticket_Contact_Email="test@example.com",
        Resolution=long_text,
    )
    assert obj.Ticket_Body == long_text
    assert obj.Resolution == long_text
