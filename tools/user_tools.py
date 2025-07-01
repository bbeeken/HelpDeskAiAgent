"""
tools/user_tools.py

Stubs for future Microsoft Graph API integration.
Uses Azure AD group ID 2ea9cf9b-4d28-456e-9eda-bd2c15825ee2.
"""

from typing import Dict, List

GROUP_ID = "2ea9cf9b-4d28-456e-9eda-bd2c15825ee2"


def get_user_by_email(email: str) -> Dict[str, str | None]:
    return {
        "email": email,
        "displayName": None,
        "id": None,
    }


def get_all_users_in_group() -> List[Dict[str, str | None]]:
    return []


def resolve_user_display_name(identifier: str) -> str:
    return identifier
