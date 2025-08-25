"""User management and on-call scheduling utilities."""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Sequence, Any
from datetime import datetime, UTC

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.repositories.models import OnCallShift

logger = logging.getLogger(__name__)

GRAPH_CLIENT_ID = os.getenv("GRAPH_CLIENT_ID")
GRAPH_CLIENT_SECRET = os.getenv("GRAPH_CLIENT_SECRET")
GRAPH_TENANT_ID = os.getenv("GRAPH_TENANT_ID")

GROUP_ID = "2ea9cf9b-4d28-456e-9eda-bd2c15825ee2"


class UserManager:
    """Handles user lookup, groups, and on-call schedule."""

    # Microsoft Graph integration -------------------------------------
    def _has_graph_creds(self) -> bool:
        return all([GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, GRAPH_TENANT_ID])

    async def _get_token(self) -> str:
        if not self._has_graph_creds():
            logger.info("Graph credentials missing, returning stub token")
            return ""
        url = f"https://login.microsoftonline.com/{GRAPH_TENANT_ID}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": GRAPH_CLIENT_ID,
            "client_secret": GRAPH_CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
        }
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, data=data, timeout=10)
                resp.raise_for_status()
            except httpx.TimeoutException as exc:
                logger.exception("Timeout fetching Graph token: %s", exc)
                raise
            except httpx.HTTPStatusError as exc:
                logger.exception("Bad status fetching Graph token: %s", exc)
                raise
            except httpx.RequestError as exc:
                logger.exception("Request error fetching Graph token: %s", exc)
                raise
            return resp.json().get("access_token", "")

    async def _graph_get(self, endpoint: str, token: str) -> dict:
        if not token:
            logger.info("No Graph token provided, returning stub data for %s", endpoint)
            return {}
        url = f"https://graph.microsoft.com/v1.0/{endpoint}"
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    url, headers={"Authorization": f"Bearer {token}"}, timeout=10
                )
                resp.raise_for_status()
            except httpx.TimeoutException as exc:
                logger.exception("Timeout calling Graph endpoint %s: %s", endpoint, exc)
                raise
            except httpx.HTTPStatusError as exc:
                logger.exception("Bad status from Graph endpoint %s: %s", endpoint, exc)
                raise
            except httpx.RequestError as exc:
                logger.exception("Request error calling Graph endpoint %s: %s", endpoint, exc)
                raise
            return resp.json()

    async def get_user_by_email(self, email: str) -> Dict[str, str | None]:
        try:
            token = await self._get_token()
            if not token:
                return {"email": email, "displayName": None, "id": None}
            data = await self._graph_get(f"users/{email}", token)
        except httpx.HTTPError:
            logger.exception("Failed to get user by email %s", email)
            return {"email": email, "displayName": None, "id": None}
        return {
            "email": data.get("mail"),
            "displayName": data.get("displayName"),
            "id": data.get("id"),
        }

    async def get_users_by_emails(
        self, emails: Sequence[str]
    ) -> Dict[str, Dict[str, str | None]]:
        """Fetch multiple user profiles, one request per unique email."""
        profiles: Dict[str, Dict[str, str | None]] = {}
        for email in set(emails):
            profiles[email] = await self.get_user_by_email(email)
        return profiles

    async def get_users_in_group(self) -> List[Dict[str, str | None]]:
        try:
            token = await self._get_token()
            if not token:
                return []
            data = await self._graph_get(f"groups/{GROUP_ID}/members", token)
        except httpx.HTTPError:
            logger.exception("Failed to get users in group")
            return []
        return [
            {"email": u.get("mail"), "displayName": u.get("displayName"), "id": u.get("id")}
            for u in data.get("value", [])
        ]

    async def resolve_display_name(self, identifier: str) -> str:
        user = await self.get_user_by_email(identifier)
        return user.get("displayName") or identifier

    # On-call schedule --------------------------------------------------
    async def get_current_oncall(self, db: AsyncSession) -> OnCallShift | None:
        now = datetime.now(UTC)
        result = await db.execute(
            select(OnCallShift)
            .where(OnCallShift.start_time <= now)
            .where(OnCallShift.end_time > now)
            .order_by(OnCallShift.start_time.desc())
            .limit(1)
        )
        shift = result.scalars().first()
        logger.info("Current on-call shift: %s", shift)
        return shift

    async def list_oncall_schedule(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 10,
        filters: Dict[str, Any] | None = None,
        sort: List[str] | None = None,
    ) -> Sequence[OnCallShift]:
        query = select(OnCallShift)
        if filters:
            for key, value in list(filters.items()):
                if key == "start_from":
                    query = query.filter(OnCallShift.start_time >= value)
                elif key == "start_to":
                    query = query.filter(OnCallShift.start_time <= value)
                elif key == "end_from":
                    query = query.filter(OnCallShift.end_time >= value)
                elif key == "end_to":
                    query = query.filter(OnCallShift.end_time <= value)
                elif hasattr(OnCallShift, key):
                    attr = getattr(OnCallShift, key)
                    query = query.filter(attr.in_(value) if isinstance(value, list) else attr == value)
        if sort:
            if isinstance(sort, str):
                sort = [sort]
            order_cols = []
            for s in sort:
                direction = "asc"
                column = s
                if s.startswith("-"):
                    column = s[1:]
                    direction = "desc"
                elif " " in s:
                    column, dir_part = s.rsplit(" ", 1)
                    if dir_part.lower() in {"asc", "desc"}:
                        direction = dir_part.lower()
                if hasattr(OnCallShift, column):
                    attr = getattr(OnCallShift, column)
                    order_cols.append(attr.desc() if direction == "desc" else attr.asc())
            if order_cols:
                query = query.order_by(*order_cols)
        else:
            query = query.order_by(OnCallShift.start_time)
        if skip:
            query = query.offset(skip)
        if limit:
            query = query.limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    # Context helpers ---------------------------------------------------
    async def get_user_context(self, email: str) -> Dict[str, Any]:
        user = await self.get_user_by_email(email)
        return {
            "email": user.get("email"),
            "displayName": user.get("displayName"),
            "id": user.get("id"),
        }

    async def is_user_in_helpdesk_group(self, email: str) -> bool:
        members = await self.get_users_in_group()
        return any(m.get("email") == email for m in members)

__all__ = ["UserManager"]

