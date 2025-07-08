"""Utilities for looking up users.

This module currently provides placeholder implementations for querying
Microsoft Graph.  The intent is to look up users and group membership in
Azure AD using Graph API endpoints.  A few helper functions are provided so
the rest of the code base can be written against a stable interface while the
Graph integration is developed.

``GROUP_ID`` refers to the Truck Stop helpdesk security group and is used when
fetching all members of that group.  When Microsoft Graph credentials are
present the helpers perform real HTTP requests.  Otherwise they return simple
stub data so the rest of the application and tests can run without network
access.

Environment variables ``GRAPH_CLIENT_ID``, ``GRAPH_CLIENT_SECRET`` and
``GRAPH_TENANT_ID`` must be provided for the real API calls.  When any of them
is missing these functions fall back to simple stubs so tests can run without
network access.
"""

from typing import Dict, List

import logging
import os
import httpx

logger = logging.getLogger(__name__)

GRAPH_CLIENT_ID = os.getenv("GRAPH_CLIENT_ID")
GRAPH_CLIENT_SECRET = os.getenv("GRAPH_CLIENT_SECRET")
GRAPH_TENANT_ID = os.getenv("GRAPH_TENANT_ID")


GROUP_ID = "2ea9cf9b-4d28-456e-9eda-bd2c15825ee2"



def _has_graph_creds() -> bool:
    """Return ``True`` when all required Graph credentials are present."""

    return all([GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, GRAPH_TENANT_ID])


async def _get_token() -> str:
    """Obtain an access token from Microsoft Graph.

    Returns:
        The token string if credentials are configured; otherwise an empty
        string when running in stub mode.
    """

    if not _has_graph_creds():
        # In test/stub mode we short-circuit so no HTTP requests are made
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
        except httpx.HTTPError as exc:
            logger.exception("Error fetching Graph token: %s", exc)
            return ""
        return resp.json()["access_token"]



async def _graph_get(endpoint: str, token: str) -> dict:
    """Perform a GET request to the Graph API.

    Args:
        endpoint: Relative Graph endpoint (e.g. ``users/me``).
        token: Bearer token obtained from :func:`_get_token`.

    Returns:
        Parsed JSON data from the API or an empty ``dict`` if no token is
        available or an HTTP error occurs.
    """

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
        except httpx.HTTPError as exc:
            logger.exception("Error calling Graph endpoint %s: %s", endpoint, exc)
            return {}
        return resp.json()



async def get_user_by_email(email: str) -> Dict[str, str | None]:
    """Look up a user by email address using Microsoft Graph.

    Args:
        email: The email address to search for.

    Returns:
        A dictionary with ``email``, ``displayName`` and ``id`` keys. Values may
        be ``None`` when running in stub mode or if the user is not found.
    """

    token = await _get_token()
    if not token:
        return {"email": email, "displayName": None, "id": None}

    data = await _graph_get(f"users/{email}", token)
    return {
        "email": data.get("mail"),
        "displayName": data.get("displayName"),
        "id": data.get("id"),
    }



async def get_all_users_in_group() -> List[Dict[str, str | None]]:
    """Return details for all members of the helpdesk security group."""

    token = await _get_token()
    if not token:
        return []

    data = await _graph_get(f"groups/{GROUP_ID}/members", token)
    return [
        {"email": u.get("mail"), "displayName": u.get("displayName"), "id": u.get("id")}
        for u in data.get("value", [])
    ]


async def resolve_user_display_name(identifier: str) -> str:
    """Return the display name for an email or identifier."""

    logger.info("Resolving display name for %s", identifier)
    user = await get_user_by_email(identifier)
    return user.get("displayName") or identifier
