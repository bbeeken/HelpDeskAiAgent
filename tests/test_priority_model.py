import pytest
from sqlalchemy import select
import src.infrastructure.database as mssql
from src.core.repositories.models import PriorityLevel


@pytest.mark.asyncio
async def test_priority_insert_select():
    async with mssql.SessionLocal() as db:
        urgent = PriorityLevel(Label="Urgent")
        db.add(urgent)
        await db.commit()
        result = await db.execute(select(PriorityLevel).where(PriorityLevel.Label == "Urgent"))
        fetched = result.scalar_one()
        assert fetched.Label == "Urgent"
