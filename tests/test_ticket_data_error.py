import logging

from fastapi.testclient import TestClient

from main import app
from src.core.services.system_utilities import OperationResult
client = TestClient(app)


def test_create_ticket_logs_dataerror_field(monkeypatch, caplog):
    """Ensure DataError details include offending field and value."""

    async def fail_create(db, obj):
        err = (
            '(psycopg2.errors.InvalidDatetimeFormat) invalid input syntax for type '
            'timestamp: "bad" [parameters: {"ValidFrom": "bad"}]'
        )
        return OperationResult(success=False, error=err)

    monkeypatch.setattr("src.api.v1.tickets.create_ticket", fail_create)

    payload = {
        "Subject": "Bad Date",
        "Ticket_Body": "body",
        "Ticket_Contact_Name": "Tester",
        "Ticket_Contact_Email": "tester@example.com",
    }

    with caplog.at_level(logging.ERROR):
        resp = client.post("/ticket", json=payload)

    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert "ValidFrom" in detail
    assert "bad" in detail
    assert any("ValidFrom" in r.message and "bad" in r.message for r in caplog.records)

