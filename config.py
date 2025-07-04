"""Application configuration loader.

This module loads environment variables from a ``.env`` file and then imports
``config_env.py`` if present. Values defined in that file override environment
variables and are exposed at the top level of this module.
"""

import importlib
import logging
import os

from dotenv import load_dotenv


load_dotenv()

DB_CONN_STRING: str | None = os.getenv("DB_CONN_STRING")

try:
    env_module = importlib.import_module("config_env")
except ModuleNotFoundError:
    logging.debug("config_env.py not found; using environment variables only")
else:
    for name, value in vars(env_module).items():
        if name.isupper():
            globals()[name] = value
