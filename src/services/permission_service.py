"""Permission Service — Android/iOS runtime media permissions.

Tri-state results: "granted" (proceed), "denied" (show rationale, may re-ask),
"permanent" (OS ignores re-requests — route to app Settings). The old bool
forced callers to guess, and both call sites guessed wrong (scanned anyway).
"""

import asyncio
import contextlib
import logging

import flet as ft

logger = logging.getLogger("permission_service")


def _platform(page) -> object:
    try:
        return page.platform if page is not None else None
    except Exception:
        return None


def _handler(page):
    """Reuse the mounted PermissionHandler (no per-call construction + leak).
    Searches page.services first; only appends when absent, with an update so
    the native binding exists before the first request."""
    from flet_permission_handler import PermissionHandler

    for service in list(getattr(page, "services", []) or []):
        if isinstance(service, PermissionHandler):
            return service
    ph = PermissionHandler()
    page.services.append(ph)
    return ph


async def _status_of(ph, permission):
    try:
        return await ph.get_status(permission)
    except Exception as ex:
        logger.debug("get_status(%s) failed: %s", permission, ex)
        return None


async def _request_with_timeout(ph, permission, timeout: float = 60.0):
    try:
        return await asyncio.wait_for(ph.request(permission), timeout=timeout)
    except TimeoutError:
        logger.info("Permission request timed out (dialog never dismissed)")
        return None
    except Exception as ex:
        logger.debug("request(%s) failed: %s", permission, ex)
        return None


async def open_app_settings(page) -> bool:
    """Open the OS app-settings page (permanent-denial recovery)."""
    try:
        from flet_permission_handler import PermissionHandler

        ph = _handler(page)
        if isinstance(ph, PermissionHandler):
            return bool(await ph.open_app_settings())
        for service in list(getattr(page, "services", []) or []):
            if hasattr(service, "open_app_settings"):
                return bool(await service.open_app_settings())
    except Exception as ex:
        logger.debug("open_app_settings failed: %s", ex)
    return False


async def request_storage_permission(page: ft.Page) -> str:
    """Request media-library permission. Returns "granted" | "denied" |
    "permanent". Off-mobile platforms return "granted" (nothing to ask).

    Flow: get_status first (never re-prompt an already-granted permission —
    every re-request risks the OS escalating to permanently-denied), then
    request() only when needed. LIMITED (Android 14+ partial / iOS limited
    library) counts as usable. SDK-aware: API 33+ asks VIDEOS only, older
    asks STORAGE only, iOS asks PHOTOS (VIDEOS-then-STORAGE wasted a
    guaranteed-failing round-trip on both).
    """
    from flet_permission_handler import Permission, PermissionStatus

    platform = _platform(page)
    if page is None:
        return "granted"
    if platform not in (
        ft.PagePlatform.ANDROID,
        ft.PagePlatform.ANDROID_TV,
        ft.PagePlatform.IOS,
    ):
        return "granted"

    try:
        from services.android_bridge import sdk_int

        api = sdk_int()
    except Exception:
        api = 0
    is_ios = platform == ft.PagePlatform.IOS
    if is_ios:
        wanted = [Permission.PHOTOS]
    elif api and api < 33:
        wanted = [Permission.STORAGE]
    else:
        # API 33+ (or unknown SDK — try the modern permission first, fall
        # back to STORAGE for good measure on failure).
        wanted = (
            [Permission.VIDEOS, Permission.STORAGE] if not api else [Permission.VIDEOS]
        )

    try:
        ph = _handler(page)
        with contextlib.suppress(Exception):
            page.update()
    except Exception as ex:
        logger.warning("Permission handler unavailable: %s", ex)
        return "denied"

    usable = (PermissionStatus.GRANTED, PermissionStatus.LIMITED)
    permanent = False
    for permission in wanted:
        status = await _status_of(ph, permission)
        logger.info("Permission %s status: %s", permission, status)
        if status in usable:
            return "granted"
        if status == PermissionStatus.PERMANENTLY_DENIED:
            # Don't re-request (OS ignores it); but later permissions in the
            # list may still be grantable — keep probing, remember permanent.
            permanent = True
            continue
        # DENIED / RESTRICTED / None / unknown: ask once, with a timeout so
        # an undismissed OS dialog can't hang the mount path forever.
        result = await _request_with_timeout(ph, permission)
        logger.info("Permission %s request: %s", permission, result)
        if result in usable:
            return "granted"
        if result == PermissionStatus.PERMANENTLY_DENIED:
            permanent = True
    if permanent:
        return "permanent"
    return "denied"
