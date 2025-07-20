import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from unittest.mock import AsyncMock

from main import app
from db.mssql import engine

# Override the autouse app_lifespan fixture from conftest
@pytest_asyncio.fixture(autouse=True)
async def app_lifespan():
    yield

@pytest.mark.asyncio
async def test_engine_disposed_on_shutdown(monkeypatch):
    dispose_mock = AsyncMock()
    monkeypatch.setattr(engine.__class__, "dispose", dispose_mock)
    async with LifespanManager(app):
        pass
    dispose_mock.assert_awaited_once()
