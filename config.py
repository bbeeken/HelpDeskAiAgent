import os
from dotenv import load_dotenv

load_dotenv()

DB_CONN_STRING: str | None = os.getenv("DB_CONN_STRING")
OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")

