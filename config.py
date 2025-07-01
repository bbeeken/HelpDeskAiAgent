import os
from dotenv import load_dotenv

load_dotenv()

DB_CONN_STRING = os.getenv("DB_CONN_STRING")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise EnvironmentError("OPENAI_API_KEY environment variable is required")
