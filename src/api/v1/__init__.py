from fastapi import FastAPI

from .deps import get_db  # re-export for external use
from .tickets import ticket_router, tickets_router
from .analytics import analytics_router
from .auth import auth_router


def register_routes(app: FastAPI) -> None:
    app.include_router(ticket_router)
    app.include_router(tickets_router)
    app.include_router(analytics_router)
    app.include_router(auth_router)

__all__ = [
    "get_db",
    "ticket_router",
    "tickets_router",
    "analytics_router",
    "auth_router",
    "register_routes",
]
