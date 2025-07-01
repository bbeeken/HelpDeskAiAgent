import importlib
import os

CONFIG_ENV = os.getenv("CONFIG_ENV", "dev").lower()
module_name = f"config_{CONFIG_ENV}"
try:
    _config = importlib.import_module(module_name)
except ImportError as exc:
    raise ImportError(f"Unknown CONFIG_ENV: {CONFIG_ENV}") from exc

for name in dir(_config):
    if name.isupper():
        globals()[name] = getattr(_config, name)

__all__ = [name for name in globals() if name.isupper()]
