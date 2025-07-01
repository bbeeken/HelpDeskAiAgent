import os

# Provide defaults so importing the app doesn't fail
os.environ.setdefault("DB_CONN_STRING", "mssql+pyodbc://user:pass@localhost/testdb?driver=ODBC+Driver+17+for+SQL+Server")
os.environ.setdefault("OPENAI_API_KEY", "test")

from main import app

def test_app_import():
    assert app.title == "Truck Stop MCP Helpdesk API"
