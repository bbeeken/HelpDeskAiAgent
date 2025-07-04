import os

# Provide defaults so importing the app doesn't fail
os.environ.setdefault("DB_CONN_STRING", "sqlite+aiosqlite:///:memory:")

from main import app


def test_app_import():
    assert app.title == "Truck Stop MCP Helpdesk API"


def test_app_loads():
    assert app.title
