import os
import logging
from dotenv import load_dotenv

load_dotenv()

DB_CONN_STRING = os.getenv("DB_CONN_STRING")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

