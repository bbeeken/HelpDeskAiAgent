import importlib
import pytest

import src.infrastructure.database as mssql


def test_pyodbc_conn_string_not_allowed(monkeypatch):
    conn = "mssql+pyodbc://user:pass@localhost/db"
    monkeypatch.setenv("DB_CONN_STRING", conn)
    monkeypatch.setattr("config.DB_CONN_STRING", conn, raising=False)
    with pytest.raises(RuntimeError):
        importlib.reload(mssql)
