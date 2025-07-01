import os
import sys
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("DB_CONN_STRING", "sqlite:///:memory:")

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from main import app

def test_app_loads():
    assert app.title
