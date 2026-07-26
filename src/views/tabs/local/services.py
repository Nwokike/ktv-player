"""Permission and service helpers for local video tab."""

import logging
import flet as ft

from services.local_scanner import get_default_scan_paths, is_mobile

logger = logging.getLogger(__name__)

_sp = None  # StoragePaths instance
_fp = None  # FilePicker instance


async def _ensure_services(page_obj):
    """Register Services once."""
    global _sp, _fp

    if _fp is None:
        try:
            _fp = ft.FilePicker()
        except Exception:
            logger.warning("FilePicker not available")

    if not is_mobile():
        page_obj.update()
        return

    if _sp is None:
        try:
            _sp = ft.StoragePaths()
        except Exception:
            logger.warning("StoragePaths not available")

    page_obj.update()


async def _request_storage_permission() -> bool:
    """Standard storage permission check."""
    return True


async def _get_scan_paths(custom_paths: list[str] = None) -> list[str]:
    """Get scan paths using StoragePaths, targeting safe media folders, plus custom paths."""
    paths = list(custom_paths) if custom_paths else []

    if is_mobile() and _sp is not None:
        try:
            ext_dir = await _sp.get_external_storage_directory()
            if ext_dir:
                paths.extend(
                    [
                        f"{ext_dir}/Movies",
                        f"{ext_dir}/Download",
                        f"{ext_dir}/DCIM",
                        f"{ext_dir}/Pictures",
                        f"{ext_dir}/Video",
                    ],
                )
        except Exception:
            pass

        try:
            dl_dir = await _sp.get_downloads_directory()
            if dl_dir:
                paths.append(dl_dir)
        except Exception:
            pass

    paths = list(dict.fromkeys(paths))
    if not paths:
        paths = get_default_scan_paths()

    return paths
