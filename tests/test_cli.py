import argparse
import io
import json

import pytest
import httpx
from httpx import AsyncClient, ASGITransport
from main import app

import src.core.services.cli as cli

import pytest_asyncio


@pytest_asyncio.fixture
def cli_setup(monkeypatch):
    transport = ASGITransport(app=app)

    def _client(*args, **kwargs):
        kwargs.setdefault("transport", transport)
        kwargs.setdefault("base_url", "http://test")
        return AsyncClient(**kwargs)

    monkeypatch.setenv("API_BASE_URL", "http://test")
    monkeypatch.setattr(cli.httpx, "AsyncClient", _client)
    yield


@pytest.mark.asyncio
async def test_create_ticket_cli(cli_setup, capsys, monkeypatch):
    payload = {
        "Subject": "CLI test",
        "Ticket_Body": "Body",
        "Ticket_Contact_Name": "Tester",
        "Ticket_Contact_Email": "t@example.com",
    }
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO(json.dumps(payload)))
    await cli.create_ticket(argparse.Namespace())
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["Subject"] == "CLI test"
    assert "Ticket_ID" in data



@pytest.mark.asyncio
async def test_create_ticket_cli_http_error(cli_setup, capsys, monkeypatch):
    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def post(self, *args, **kwargs):
            raise httpx.HTTPError("fail")

    monkeypatch.setattr(cli.httpx, "AsyncClient", lambda *a, **k: FailingClient())
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("{}"))
    await cli.create_ticket(argparse.Namespace())
    assert capsys.readouterr().out == ""


