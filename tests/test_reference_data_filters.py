import pytest
from datetime import datetime, UTC

from db.mssql import SessionLocal
from db.models import Asset, Vendor, Site, Ticket
from tools import asset_tools, vendor_tools, site_tools, ticket_tools


@pytest.mark.asyncio
async def test_asset_vendor_site_filters_and_sort():
    async with SessionLocal() as db:
        a1 = Asset(Label="A1", Site_ID=1)
        a2 = Asset(Label="A2", Site_ID=2)
        v1 = Vendor(Name="V1")
        v2 = Vendor(Name="V2")
        s1 = Site(Label="S1")
        s2 = Site(Label="S2")
        db.add_all([a1, a2, v1, v2, s1, s2])
        await db.commit()
        await db.refresh(a1); await db.refresh(a2)
        await db.refresh(v1); await db.refresh(v2)
        await db.refresh(s1); await db.refresh(s2)

        assets = await asset_tools.list_assets(db, filters={"Site_ID": 2})
        assert [a.ID for a in assets] == [a2.ID]

        vendors = await vendor_tools.list_vendors(db, sort=["-ID"])
        assert [v.ID for v in vendors][:2] == [v2.ID, v1.ID]

        sites = await site_tools.list_sites(db, filters={"ID": [s1.ID, s2.ID]}, sort=["-Label"])
        assert [s.Label for s in sites] == sorted([s1.Label, s2.Label], reverse=True)


@pytest.mark.asyncio
async def test_ticket_list_filters_and_sort():
    async with SessionLocal() as db:
        t1 = Ticket(
            Subject="F1",
            Ticket_Body="b",
            Ticket_Contact_Name="n",
            Ticket_Contact_Email="e",
            Created_Date=datetime(2023, 1, 1, tzinfo=UTC),
        )
        t2 = Ticket(
            Subject="F2",
            Ticket_Body="b",
            Ticket_Contact_Name="n",
            Ticket_Contact_Email="e",
            Created_Date=datetime(2023, 1, 2, tzinfo=UTC),
        )
        await ticket_tools.create_ticket(db, t1)
        await ticket_tools.create_ticket(db, t2)

        res = await ticket_tools.list_tickets_expanded(db, filters={"Subject": "F2"})
        assert len(res) == 1 and res[0].Subject == "F2"

        ordered = await ticket_tools.list_tickets_expanded(db, sort=["-Created_Date"])
        ids = [t.Ticket_ID for t in ordered]
        assert ids == sorted(ids, reverse=True)
