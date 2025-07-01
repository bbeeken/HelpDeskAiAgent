import pytest
from ai import openai_agent


def test_suggest_ticket_response_requires_key(monkeypatch):
    monkeypatch.setattr(openai_agent, "OPENAI_API_KEY", None)
    with pytest.raises(RuntimeError):
        openai_agent.suggest_ticket_response({"Subject": "Test", "Ticket_Body": "body"})
