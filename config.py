import os
from dotenv import load_dotenv

load_dotenv()

DB_CONN_STRING = os.getenv("DB_CONN_STRING")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Microsoft Graph configuration. When all variables are present
# functions in ``tools.user_tools`` may attempt to contact the Graph API.
GRAPH_CLIENT_ID = os.getenv("GRAPH_CLIENT_ID")
GRAPH_CLIENT_SECRET = os.getenv("GRAPH_CLIENT_SECRET")
GRAPH_TENANT_ID = os.getenv("GRAPH_TENANT_ID")
GRAPH_ENABLED = all(
    [GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, GRAPH_TENANT_ID]
)

