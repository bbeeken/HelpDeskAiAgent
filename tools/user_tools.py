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

from typing import List, Dict
import requests

from config import (
    GRAPH_CLIENT_ID,
    GRAPH_CLIENT_SECRET,
    GRAPH_TENANT_ID,
    GRAPH_ENABLED,
)

GROUP_ID = "2ea9cf9b-4d28-456e-9eda-bd2c15825ee2"


def _acquire_token() -> str | None:
    """Return an access token if Graph integration is configured."""
    if not GRAPH_ENABLED:
        return None

    # TODO: handle token caching/expiry when implementing full support
    url = f"https://login.microsoftonline.com/{GRAPH_TENANT_ID}/oauth2/v2.0/token"
    data = {
        "client_id": GRAPH_CLIENT_ID,
        "client_secret": GRAPH_CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }

    resp = requests.post(url, data=data, timeout=5)
    resp.raise_for_status()
    return resp.json().get("access_token")


def get_user_by_email(email: str) -> Dict:
    """Return user information for ``email`` using Microsoft Graph when configured."""
    if not GRAPH_ENABLED:
        # TODO: replace with real call to ``/users/{email}``
        return {
            "email": email,
            "displayName": None,
            "id": None,
        }

    token = _acquire_token()
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(
        f"https://graph.microsoft.com/v1.0/users/{email}",
        headers=headers,
        timeout=5,
    )
    if resp.status_code == 404:
        return {"email": email, "displayName": None, "id": None}
    resp.raise_for_status()
    data = resp.json()
    return {
        "email": data.get("mail"),
        "displayName": data.get("displayName"),
        "id": data.get("id"),
    }


def get_all_users_in_group() -> List[Dict]:
    """Return all users in ``GROUP_ID`` when Graph integration is enabled."""
    if not GRAPH_ENABLED:
        # TODO: replace with real call to ``/groups/{GROUP_ID}/members``
        return []

    token = _acquire_token()
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(
        f"https://graph.microsoft.com/v1.0/groups/{GROUP_ID}/members",
        headers=headers,
        timeout=5,
    )
    resp.raise_for_status()
    return [
        {
            "email": item.get("mail"),
            "displayName": item.get("displayName"),
            "id": item.get("id"),
        }
        for item in resp.json().get("value", [])
    ]


def resolve_user_display_name(identifier: str) -> str:
    """Return a display name for ``identifier``."""
    if GRAPH_ENABLED:
        user = get_user_by_email(identifier)
        return user.get("displayName") or identifier
    return identifier
