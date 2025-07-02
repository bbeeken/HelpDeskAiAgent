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

import os
import requests

import logging

logger = logging.getLogger(__name__)


GROUP_ID = "2ea9cf9b-4d28-456e-9eda-bd2c15825ee2"


GRAPH_CLIENT_ID = os.getenv("GRAPH_CLIENT_ID")
GRAPH_CLIENT_SECRET = os.getenv("GRAPH_CLIENT_SECRET")
GRAPH_TENANT_ID = os.getenv("GRAPH_TENANT_ID")


def _get_token() -> str | None:
    if not (GRAPH_CLIENT_ID and GRAPH_CLIENT_SECRET and GRAPH_TENANT_ID):
        return None

    url = (
        f"https://login.microsoftonline.com/{GRAPH_TENANT_ID}/oauth2/v2.0/token"
    )
    resp = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": GRAPH_CLIENT_ID,
            "client_secret": GRAPH_CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json().get("access_token")


def get_user_by_email(email: str) -> Dict[str, str | None]:
    token = _get_token()
    if not token:
        data = {"mail": email, "displayName": None, "id": None}
    else:
        resp = requests.get(
            f"https://graph.microsoft.com/v1.0/users/{email}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()

    return {
        "email": data.get("mail"),
        "displayName": data.get("displayName"),
        "id": data.get("id"),
    }



def get_all_users_in_group() -> List[Dict[str, str | None]]:
    token = _get_token()
    if not token:
        return []

    resp = requests.get(
        f"https://graph.microsoft.com/v1.0/groups/{GROUP_ID}/members",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5,
    )
    resp.raise_for_status()
    values = resp.json().get("value", [])
    return [
        {"email": u.get("mail"), "displayName": u.get("displayName"), "id": u.get("id")}
        for u in values
    ]


def resolve_user_display_name(identifier: str) -> str:
    logger.info("Resolving display name for %s", identifier)
    user = get_user_by_email(identifier)
    return user.get("displayName") or identifier

