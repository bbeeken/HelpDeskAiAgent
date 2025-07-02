from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def _patch_openai(monkeypatch):
    class DummyClient:
        class Chat:
            class Completions:
                @staticmethod
                def create(*args, **kwargs):
                    return {"choices": [{"message": {"content": "ok"}}]}

            completions = Completions()

        chat = Chat()

    from ai import openai_agent
    monkeypatch.setattr(openai_agent, "openai_client", DummyClient())

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

