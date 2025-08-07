import pytest
from sqlalchemy import select
import src.infrastructure.database as mssql
from src.core.repositories.models import Priority


@pytest.mark.asyncio
async def test_priority_insert_select():
    async with mssql.SessionLocal() as db:
        urgent = Priority(Label="Urgent")
        db.add(urgent)
        await db.commit()
        result = await db.execute(select(Priority).where(Priority.Label == "Urgent"))
        fetched = result.scalar_one()
        assert fetched.Label == "Urgent"
