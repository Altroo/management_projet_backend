"""
Permission utilities for management_projet app.

Access model:
- is_staff users: always granted full access regardless of flags
- Regular authenticated users: access determined by per-user boolean flags
  (can_view, can_create, can_edit, can_delete on CustomUser)
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from account.models import CustomUser


def can_view(user: "CustomUser") -> bool:
    """Staff always allowed; others need can_view flag (defaults True)."""
    return user.is_staff or user.can_view


def can_create(user: "CustomUser") -> bool:
    """Staff always allowed; others need can_create flag (defaults False)."""
    return user.is_staff or user.can_create


def can_update(user: "CustomUser") -> bool:
    """Staff always allowed; others need can_edit flag (defaults False)."""
    return user.is_staff or user.can_edit


def can_delete(user: "CustomUser") -> bool:
    """Staff always allowed; others need can_delete flag (defaults False)."""
    return user.is_staff or user.can_delete
