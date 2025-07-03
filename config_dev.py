import os
from dotenv import load_dotenv

load_dotenv()

DB_CONN_STRING = os.getenv("DB_CONN_STRING")
