from fastapi import FastAPI

from .deps import get_db, get_db_with_commit  # re-export for external use
from .tickets import ticket_router
from .analytics import analytics_router
from .auth import auth_router


def register_routes(app: FastAPI) -> None:
    app.include_router(ticket_router)
    app.include_router(analytics_router)
    app.include_router(auth_router)

__all__ = [
    "get_db",
    "get_db_with_commit",
    "ticket_router",
    "analytics_router",
    "auth_router",
    "register_routes",
]
