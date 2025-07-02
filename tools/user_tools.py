"""Utilities for looking up users.

This module currently provides placeholder implementations for querying
Microsoft Graph.  The intent is to look up users and group membership in
Azure AD using Graph API endpoints.  A few helper functions are provided so
the rest of the code base can be written against a stable interface while the
Graph integration is developed.

``GROUP_ID`` refers to the Truck Stop helpdesk security group and is used when
fetching all members of that group.

TODO:

* Acquire an OAuth token using the client credentials flow via
  ``https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token``.
* Query ``GET https://graph.microsoft.com/v1.0/users/{email}`` to fetch a
  single user.
* Query ``GET https://graph.microsoft.com/v1.0/groups/{GROUP_ID}/members`` to
  list all group users.

Environment variables ``GRAPH_CLIENT_ID``, ``GRAPH_CLIENT_SECRET`` and
``GRAPH_TENANT_ID`` must be provided for the real API calls.  When any of them
is missing these functions fall back to simple stubs so tests can run without
network access.
"""

from typing import Dict, List

import logging
import os
import requests

logger = logging.getLogger(__name__)


GROUP_ID = "2ea9cf9b-4d28-456e-9eda-bd2c15825ee2"

CLIENT_ID = os.getenv("GRAPH_CLIENT_ID")
CLIENT_SECRET = os.getenv("GRAPH_CLIENT_SECRET")
TENANT_ID = os.getenv("GRAPH_TENANT_ID")


def _get_token() -> str | None:
    if not (CLIENT_ID and CLIENT_SECRET and TENANT_ID):
        return None

    url = (
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    )
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }
    resp = requests.post(url, data=data, timeout=10)
    resp.raise_for_status()
    return resp.json().get("access_token")


def get_user_by_email(email: str) -> Dict[str, str | None]:
    """Return details for a single user identified by email."""

    token = _get_token()
    if not token:
        return {"email": email, "displayName": None, "id": None}

    url = f"https://graph.microsoft.com/v1.0/users/{email}"
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "email": data.get("mail"),
        "displayName": data.get("displayName"),
        "id": data.get("id"),
    }



def get_all_users_in_group() -> List[Dict[str, str | None]]:
    """Return all members of the helpdesk group."""

    token = _get_token()
    if not token:
        return []

    url = f"https://graph.microsoft.com/v1.0/groups/{GROUP_ID}/members"
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    payload = resp.json()
    users = []
    for data in payload.get("value", []):
        users.append(
            {
                "email": data.get("mail"),
                "displayName": data.get("displayName"),
                "id": data.get("id"),
            }
        )
    return users


def resolve_user_display_name(identifier: str) -> str:
    logger.info("Resolving display name for %s", identifier)

    user = get_user_by_email(identifier)
    return user.get("displayName") or identifier

