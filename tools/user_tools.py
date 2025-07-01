"""
tools/user_tools.py

Stubs for future Microsoft Graph API integration.
Uses Azure AD group ID 2ea9cf9b-4d28-456e-9eda-bd2c15825ee2.
"""

from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

GROUP_ID = "2ea9cf9b-4d28-456e-9eda-bd2c15825ee2"


def get_user_by_email(email: str) -> Dict:
    logger.info("Resolving user by email %s", email)
    return {
        "email": email,
        "displayName": None,
        "id": None,
    }


def get_all_users_in_group() -> List[Dict]:
    logger.info("Fetching all users in group")
    return []


def resolve_user_display_name(identifier: str) -> str:
    logger.info("Resolving display name for %s", identifier)
    return identifier

