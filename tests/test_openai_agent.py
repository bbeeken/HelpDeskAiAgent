import os
import pytest

from ai import openai_agent
import config
import importlib


def test_require_api_key_missing(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", None)
    importlib.reload(openai_agent)
    with pytest.raises(EnvironmentError):
        openai_agent.suggest_ticket_response({"Subject": "Test"})
