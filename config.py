"""Application configuration loader."""

from __future__ import annotations

import importlib
import logging
from dotenv import load_dotenv
from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)
load_dotenv()


class Settings(BaseSettings):
    """Configuration loaded from environment variables."""

    DB_CONN_STRING: str
    ERROR_TRACKING_DSN: str | None = None
    GRAPH_CLIENT_ID: str | None = None
    GRAPH_CLIENT_SECRET: str | None = None
    GRAPH_TENANT_ID: str | None = None
    ENABLE_RATE_LIMITING: bool = True
    API_BASE_URL: str = "http://localhost:8000"

    DEFAULT_TIMEZONE: str = "UTC"
    ASSUME_NAIVE_AS_UTC: bool = True

    @field_validator("DB_CONN_STRING")
    @classmethod
    def validate_db_conn_string(cls, value: str) -> str:
        if not value:
            raise ValueError("DB_CONN_STRING must not be empty")
        if value.startswith("mssql+pyodbc"):
            raise ValueError("Synchronous driver 'mssql+pyodbc' is not supported")
        return value

    @field_validator("DEFAULT_TIMEZONE")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone string."""
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(v)
            return v
        except Exception:
            if v not in ["UTC", "GMT"]:
                logger.warning(f"Timezone {v} may not be valid, using UTC")
                return "UTC"
            return v

    @field_validator("API_BASE_URL")
    @classmethod
    def validate_api_base_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("API_BASE_URL must start with http:// or https://")
        return value.rstrip("/")

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        validate_assignment=True,
        extra="ignore",
    )


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
DEFAULT_TIMEZONE = settings.DEFAULT_TIMEZONE
ASSUME_NAIVE_AS_UTC = settings.ASSUME_NAIVE_AS_UTC

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
    "DEFAULT_TIMEZONE",
    "ASSUME_NAIVE_AS_UTC",
]
