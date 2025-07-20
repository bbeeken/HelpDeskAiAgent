"""Application configuration loader."""

from __future__ import annotations

import importlib
import logging

from dotenv import load_dotenv
from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    """Configuration loaded from environment variables."""

    DB_CONN_STRING: str | None = None
    ERROR_TRACKING_DSN: str | None = None
    GRAPH_CLIENT_ID: str | None = None
    GRAPH_CLIENT_SECRET: str | None = None
    GRAPH_TENANT_ID: str | None = None
    ENABLE_RATE_LIMITING: bool = True
    API_BASE_URL: str = "http://localhost:8000"

    @field_validator("DB_CONN_STRING")
    @classmethod
    def check_async_driver(cls, value: str | None) -> str | None:
        if value and value.startswith("mssql+pyodbc"):
            raise ValueError("Synchronous driver 'mssql+pyodbc' is not supported")
        return value

    class Config:
        case_sensitive = False
        env_file = ".env"


try:
    settings = Settings()
except ValidationError as exc:  # pragma: no cover - fail fast on invalid config
    logging.error("Invalid configuration: %s", exc)
    raise

try:
    env_module = importlib.import_module("config_env")
except ModuleNotFoundError:
    logging.debug("config_env.py not found; using environment variables only")
else:
    overrides = {k: v for k, v in vars(env_module).items() if k.isupper()}
    if overrides:
        settings = Settings(**{**settings.model_dump(), **overrides})

DB_CONN_STRING = settings.DB_CONN_STRING
ERROR_TRACKING_DSN = settings.ERROR_TRACKING_DSN
GRAPH_CLIENT_ID = settings.GRAPH_CLIENT_ID
GRAPH_CLIENT_SECRET = settings.GRAPH_CLIENT_SECRET
GRAPH_TENANT_ID = settings.GRAPH_TENANT_ID
ENABLE_RATE_LIMITING = settings.ENABLE_RATE_LIMITING
API_BASE_URL = settings.API_BASE_URL

__all__ = [
    "Settings",
    "settings",
    "DB_CONN_STRING",
    "ERROR_TRACKING_DSN",
    "GRAPH_CLIENT_ID",
    "GRAPH_CLIENT_SECRET",
    "GRAPH_TENANT_ID",
    "ENABLE_RATE_LIMITING",
    "API_BASE_URL",
]
