import os

# Provide defaults so importing the app doesn't fail
os.environ.setdefault("DB_CONN_STRING", "sqlite+aiosqlite:///:memory:")

from main import app
from asgi_lifespan import LifespanManager
import pytest


def test_app_import():
    assert app.title == "Truck Stop MCP Helpdesk API"


def test_app_loads():
    assert app.title


@pytest.mark.asyncio
async def test_app_startup():
    async with LifespanManager(app):
        assert hasattr(app.state, "mcp")
