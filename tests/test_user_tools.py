import importlib
from types import SimpleNamespace

import pytest


def reload_module(monkeypatch, **env):
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    import config
    import tools.user_tools as ut
    importlib.reload(config)
    return importlib.reload(ut)


@pytest.mark.asyncio
async def test_user_tools_stub(monkeypatch):
    ut = reload_module(
        monkeypatch,
        GRAPH_CLIENT_ID=None,
        GRAPH_CLIENT_SECRET=None,
        GRAPH_TENANT_ID=None,
    )

    assert await ut.get_user_by_email("x@example.com") == {
        "email": "x@example.com",
        "displayName": None,
        "id": None,
    }
    assert await ut.get_all_users_in_group() == []
    assert await ut.resolve_user_display_name("x@example.com") == "x@example.com"


@pytest.mark.asyncio
async def test_user_tools_graph_calls(monkeypatch):
    ut = reload_module(
        monkeypatch,
        GRAPH_CLIENT_ID="id",
        GRAPH_CLIENT_SECRET="secret",
        GRAPH_TENANT_ID="tenant",
    )


    class DummyResponse(SimpleNamespace):
        def raise_for_status(self):
            pass

        def json(self):
            return self.data

    class DummyClient:

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):

            pass

        async def post(self, url, data=None, timeout=None):
            assert "tenant" in url
            return SimpleNamespace(
                status_code=200,
                raise_for_status=lambda: None,
                json=lambda: {"access_token": "tok"},
            )

        async def get(self, url, headers=None, timeout=None):
            assert headers["Authorization"] == "Bearer tok"
            if "groups" in url:
                data = {"value": [{"mail": "a@b.com", "displayName": "A", "id": "1"}]}
            else:
                data = {"mail": "u@e.com", "displayName": "U", "id": "2"}

            return SimpleNamespace(
                status_code=200,
                raise_for_status=lambda: None,
                json=lambda: data,
            )


    FakeAsyncClient = DummyClient

    monkeypatch.setattr(ut.httpx, "AsyncClient", FakeAsyncClient)



    user = await ut.get_user_by_email("u@e.com")
    assert user == {"email": "u@e.com", "displayName": "U", "id": "2"}

    users = await ut.get_all_users_in_group()
    assert users == [{"email": "a@b.com", "displayName": "A", "id": "1"}]

    assert await ut.resolve_user_display_name("u@e.com") == "U"
