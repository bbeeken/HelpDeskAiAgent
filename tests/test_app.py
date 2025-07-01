import os

os.environ.setdefault("DB_CONN_STRING", "sqlite:///:memory:")

from main import app


def test_app_import():
    assert app.title == "Truck Stop MCP Helpdesk API"
