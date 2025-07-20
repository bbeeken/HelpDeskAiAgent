"""Deprecated - use :mod:`tools.user_services` instead."""

from __future__ import annotations

import warnings
from typing import Dict, List

from .user_services import UserManager

_manager = UserManager()


async def get_user_by_email(email: str) -> Dict[str, str | None]:
    warnings.warn(
        "get_user_by_email is deprecated; use UserManager.get_user_by_email",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.get_user_by_email(email)


async def get_all_users_in_group() -> List[Dict[str, str | None]]:
    warnings.warn(
        "get_all_users_in_group is deprecated; use UserManager.get_users_in_group",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.get_users_in_group()


async def resolve_user_display_name(identifier: str) -> str:
    warnings.warn(
        "resolve_user_display_name is deprecated; use UserManager.resolve_display_name",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _manager.resolve_display_name(identifier)
