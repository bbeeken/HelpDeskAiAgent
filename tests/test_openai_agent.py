import pytest
from ai import openai_agent


def test_suggest_ticket_response_requires_key(monkeypatch):
    monkeypatch.setattr(openai_agent, "openai_client", None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        openai_agent.suggest_ticket_response({"Subject": "Test", "Ticket_Body": "body"})


def test_client_initialized_once(monkeypatch):
    """openai.Client should be instantiated only once."""
    monkeypatch.setenv("OPENAI_API_KEY", "abc")

    call_count = 0

    class DummyClient:
        def __init__(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1

            class Chat:
                class Completions:
                    @staticmethod
                    def create(*_, **__):
                        class Msg:
                            content = "ok"

                        class Choice:
                            message = Msg()

                        return type("Resp", (), {"choices": [Choice()]})()

                completions = Completions()

            self.chat = Chat()

    import importlib
    import openai

    monkeypatch.setattr(openai, "OpenAI", DummyClient)
    oa = importlib.reload(openai_agent)

    # Call multiple times; initialization should only happen once
    assert oa.suggest_ticket_response({"Subject": "s", "Ticket_Body": "b"}) == "ok"
    assert oa.suggest_ticket_response({"Subject": "s", "Ticket_Body": "b"}) == "ok"
    assert call_count == 1

    # Reload module back to default for other tests
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    importlib.reload(openai_agent)
