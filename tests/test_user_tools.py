import importlib
from types import SimpleNamespace
import httpx

import pytest


def reload_module(monkeypatch, **env):
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    import config
    import tools.user_services as us
    importlib.reload(config)
    return importlib.reload(us)


@pytest.mark.asyncio
async def test_user_tools_stub(monkeypatch):
    us = reload_module(
        monkeypatch,
        GRAPH_CLIENT_ID=None,
        GRAPH_CLIENT_SECRET=None,
        GRAPH_TENANT_ID=None,
    )
    um = us.UserManager()

    assert await um.get_user_by_email("x@example.com") == {
        "email": "x@example.com",
        "displayName": None,
        "id": None,
    }
    assert await um.get_users_in_group() == []
    assert await um.resolve_display_name("x@example.com") == "x@example.com"

    # internal helpers should short-circuit without HTTP requests
    assert await um._get_token() == ""
    assert await um._graph_get("users/x@example.com", "") == {}


@pytest.mark.asyncio
async def test_user_tools_graph_calls(monkeypatch):
    us = reload_module(
        monkeypatch,
        GRAPH_CLIENT_ID="id",
        GRAPH_CLIENT_SECRET="secret",
        GRAPH_TENANT_ID="tenant",
    )
    um = us.UserManager()

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

    monkeypatch.setattr(us.httpx, "AsyncClient", FakeAsyncClient)



    token = await um._get_token()

    assert token == "tok"

    user = await um.get_user_by_email("u@e.com")
    assert user == {"email": "u@e.com", "displayName": "U", "id": "2"}

    users = await um.get_users_in_group()
    assert users == [{"email": "a@b.com", "displayName": "A", "id": "1"}]

    assert await um.resolve_display_name("u@e.com") == "U"

    # direct call to graph_get with token
    assert await um._graph_get("users/u@e.com", token) == {
        "mail": "u@e.com",
        "displayName": "U",
        "id": "2",
    }


@pytest.mark.asyncio
async def test_user_tools_http_error(monkeypatch):
    us = reload_module(
        monkeypatch,
        GRAPH_CLIENT_ID="id",
        GRAPH_CLIENT_SECRET="secret",
        GRAPH_TENANT_ID="tenant",
    )
    um = us.UserManager()

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def post(self, url, data=None, timeout=None):
            raise httpx.HTTPError("fail")

        async def get(self, url, headers=None, timeout=None):
            raise httpx.HTTPError("fail")

    monkeypatch.setattr(us.httpx, "AsyncClient", DummyClient)

    token = await um._get_token()
    assert token == ""

    data = await um._graph_get("users/x", "tok")
    assert data == {}
