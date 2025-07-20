import logging
from typing import Any, AsyncGenerator, Dict, Sequence

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database import SessionLocal

logger = logging.getLogger(__name__)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a SQLAlchemy AsyncSession, ensuring proper cleanup."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def extract_filters(
    request: Request,
    exclude: Sequence[str] = (
        "skip",
        "limit",
        "sort",
        "sla_days",
        "status_id",
    ),
) -> Dict[str, Any]:
    """Extract arbitrary query parameters for filtering, excluding reserved keys."""
    return {
        key: value
        for key, value in request.query_params.multi_items()
        if key not in exclude
    }
