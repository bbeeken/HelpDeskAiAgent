import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timedelta, UTC

from main import app
from db.models import OnCallShift
from db.mssql import SessionLocal
from tools.oncall_tools import list_oncall_schedule


async def _add_shift(email: str, start: datetime, end: datetime) -> OnCallShift:
    async with SessionLocal() as db:
        shift = OnCallShift(user_email=email, start_time=start, end_time=end)
        db.add(shift)
        await db.commit()
        await db.refresh(shift)
        return shift


@pytest.mark.asyncio
async def test_list_oncall_schedule():
    now = datetime.now(UTC)
    await _add_shift("a@example.com", now - timedelta(hours=2), now - timedelta(hours=1))
    await _add_shift("b@example.com", now + timedelta(hours=1), now + timedelta(hours=2))

    async with SessionLocal() as db:
        schedule = await list_oncall_schedule(db)
        emails = [s.user_email for s in schedule]

    assert emails == ["a@example.com", "b@example.com"]


@pytest.mark.asyncio
async def test_oncall_schedule_filters_and_sort():
    now = datetime.now(UTC)
    s1 = await _add_shift("x@example.com", now + timedelta(hours=1), now + timedelta(hours=2))
    s2 = await _add_shift("y@example.com", now + timedelta(hours=3), now + timedelta(hours=4))

    async with SessionLocal() as db:
        filtered = await list_oncall_schedule(db, filters={"user_email": "y@example.com"})
        assert [s.user_email for s in filtered] == ["y@example.com"]

        ordered = await list_oncall_schedule(db, sort=["-start_time"])
        assert [s.id for s in ordered][:2] == [s2.id, s1.id]


@pytest.mark.asyncio
async def test_get_current_oncall_route():
    now = datetime.now(UTC)
    await _add_shift("active@example.com", now - timedelta(minutes=30), now + timedelta(minutes=30))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/oncall")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_email"] == "active@example.com"
