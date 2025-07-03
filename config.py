"""Application configuration loader.

This module loads environment variables from a ``.env`` file and then imports
``config_{env}.py`` based on the ``CONFIG_ENV`` environment variable.  Values
defined in the imported module are exposed at the top level of this module.
"""

import importlib
import logging
import os

from dotenv import load_dotenv


load_dotenv()

CONFIG_ENV = os.getenv("CONFIG_ENV", "dev")

DB_CONN_STRING: str | None = os.getenv("DB_CONN_STRING")

try:
    env_module = importlib.import_module(f"config_{CONFIG_ENV}")
except ModuleNotFoundError:
    logging.warning("config_%s.py not found; using environment variables only", CONFIG_ENV)
else:
    for name, value in vars(env_module).items():
        if name.isupper():
            globals()[name] = value
