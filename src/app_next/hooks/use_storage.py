"""Async storage facade for app_next components.

Wraps `database.manager.db_manager` so callers do not import the manager
directly. This is NOT a React-style hook — it's a thin factory returning
a `Storage` record. Components call `await use_storage().set_setting(...)`.

Keeping it a plain callable (not wrapped in @ft.component machinery) means
it can be used outside of component render cycles too (e.g. from utility
modules). It is named `use_storage` only to match the convention used by
the design spec; functionally it is a singleton accessor.
"""

from dataclasses import dataclass
from typing import Any

from database.manager import db_manager


@dataclass
class Storage:
    """Subset of db_manager that components need. Extend per milestone."""

    async def set_setting(self, key: str, value: str) -> None:
        await db_manager.set_setting(key, value)

    async def get_setting(self, key: str, default: Any = None) -> str | None:
        return await db_manager.get_setting(key, default=default)


def use_storage() -> Storage:
    """Return a Storage facade. Stateless — safe to call on every render."""
    return Storage()
