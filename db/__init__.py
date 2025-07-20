# Compatibility package for legacy imports
from .mssql import SessionLocal, engine

__all__ = ["SessionLocal", "engine"]
