"""Permission Service — requests Android OS runtime storage/video permissions."""

import logging

import flet as ft

logger = logging.getLogger("permission_service")


async def request_storage_permission(page: ft.Page) -> bool:
    """Request standard Android OS storage/video runtime permissions."""
    if not page or not hasattr(page, "platform"):
        return True

    try:
        # is_mobile() is False for ANDROID_TV — TVs need the same runtime
        # media permissions phones do, so excluding them skipped the prompt
        # entirely and left scanning to luck.
        if page.platform not in (
            ft.PagePlatform.ANDROID,
            ft.PagePlatform.ANDROID_TV,
            ft.PagePlatform.IOS,
        ):
            return True
    except Exception:
        return True

    try:
        from flet_permission_handler import (
            Permission,
            PermissionHandler,
            PermissionStatus,
        )

        ph = getattr(page, "permission_handler", None)
        if ph is None:
            ph = PermissionHandler()
            if hasattr(page, "services"):
                page.services.append(ph)
            page.permission_handler = ph

        # Android 13+ strict Media permission
        try:
            status = await ph.request(Permission.VIDEOS)
            if status == PermissionStatus.GRANTED:
                logger.info("Permission.VIDEOS granted")
                return True
        except Exception as e:
            logger.debug("Permission.VIDEOS request exception: %s", e)

        # Fallback for Android 10 and below
        try:
            status = await ph.request(Permission.STORAGE)
            if status == PermissionStatus.GRANTED:
                logger.info("Permission.STORAGE granted")
                return True
        except Exception as e:
            logger.debug("Permission.STORAGE request exception: %s", e)

        # Nothing was granted. Reporting True here told callers the scan
        # could proceed when Android had said no.
        logger.info("Storage permission not granted (user declined or denied)")
        return False
    except Exception as ex:
        logger.warning("Runtime permission request failed: %s", ex)
        return False
