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


# Microsoft Graph configuration. When all variables are present
# functions in ``tools.user_tools`` may attempt to contact the Graph API.
GRAPH_CLIENT_ID = os.getenv("GRAPH_CLIENT_ID")
GRAPH_CLIENT_SECRET = os.getenv("GRAPH_CLIENT_SECRET")
GRAPH_TENANT_ID = os.getenv("GRAPH_TENANT_ID")
GRAPH_ENABLED = all(
    [GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, GRAPH_TENANT_ID]
)

__all__ = [name for name in globals() if name.isupper()]
