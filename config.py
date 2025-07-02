import importlib
import os

import logging
from dotenv import load_dotenv


load_dotenv()

CONFIG_ENV = os.getenv("CONFIG_ENV", "dev").lower()

_env_map = {
    "dev": "config_dev",
    "staging": "config_staging",
    "prod": "config_prod",
}

module_name = _env_map.get(CONFIG_ENV, "config_dev")
if CONFIG_ENV not in _env_map:
    logging.getLogger(__name__).warning(
        "Unknown CONFIG_ENV '%s', defaulting to dev", CONFIG_ENV
    )

_settings = importlib.import_module(module_name)

DB_CONN_STRING: str | None = getattr(_settings, "DB_CONN_STRING", None)
OPENAI_API_KEY: str | None = getattr(_settings, "OPENAI_API_KEY", None)
OPENAI_MODEL_NAME: str | None = getattr(_settings, "OPENAI_MODEL_NAME", None)
OPENAI_TIMEOUT: int | None = getattr(_settings, "OPENAI_TIMEOUT", None)


