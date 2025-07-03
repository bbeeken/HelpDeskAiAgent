from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def _patch_openai(monkeypatch):
    from ai import openai_agent

    class DummyClient:
        class Chat:
            class Completions:
                @staticmethod
                async def create(*args, **kwargs):
                    class Msg:
                        content = "ok"

                    class Choice:
                        message = Msg()

                    return type("Resp", (), {"choices": [Choice()]})()

            completions = Completions()

        chat = Chat()

    openai_agent.set_client(DummyClient())

def _create_ticket():
    payload = {
        "Subject": "Rate", "Ticket_Body": "body",
        "Ticket_Contact_Name": "Tester", "Ticket_Contact_Email": "t@example.com"
    }
    resp = client.post("/ticket", json=payload)
    assert resp.status_code == 200
    return resp.json()

def test_ai_suggest_response_rate_limit(monkeypatch):
    _patch_openai(monkeypatch)
    from limiter import limiter
    limiter.reset()
    ticket = _create_ticket()
    # First 10 requests succeed
    for _ in range(10):
        r = client.post("/ai/suggest_response", json=ticket)
        assert r.status_code == 200
    # 11th request is blocked
    r = client.post("/ai/suggest_response", json=ticket)
    assert r.status_code == 429
