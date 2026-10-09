"""Crash reporter — logs unhandled exceptions to disk with rotation.

Filenames carry timestamp (microseconds) + PID and are created with mode
"x" so two crashes in the same microsecond can never overwrite each
other — the second write retries with a counter suffix.
"""

import asyncio
import datetime
import logging
import os
import platform
import traceback
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_crash_dir() -> str:
    """Crash log directory, anchored to the app — never the bare CWD.

    On Android uses FLET_APP_STORAGE_DATA; elsewhere a "storage/crashes"
    folder next to the ``src/`` package dir, so launching from a different
    working directory still lands crashes in the same place.
    """
    storage_data = os.environ.get("FLET_APP_STORAGE_DATA")
    if storage_data:
        return os.path.join(storage_data, "crashes")
    app_root = Path(__file__).resolve().parents[2]
    return str(app_root / "storage" / "crashes")


MAX_CRASH_FILES = 10


def _ensure_crash_dir() -> bool:
    try:
        os.makedirs(_get_crash_dir(), exist_ok=True)
        return True
    except OSError:
        logger.debug("Could not create crash dir", exc_info=True)
        return False


def _cleanup_old_crashes() -> None:
    """Keep the newest MAX_CRASH_FILES logs (oldest deleted first)."""
    crash_dir = _get_crash_dir()
    try:
        files = sorted(
            (f for f in os.listdir(crash_dir) if f.endswith(".log")),
            key=lambda f: os.path.getmtime(os.path.join(crash_dir, f)),
        )
        while len(files) > MAX_CRASH_FILES:
            try:
                os.remove(os.path.join(crash_dir, files.pop(0)))
            except OSError:
                logger.debug("Could not remove old crash log", exc_info=True)
                break
    except OSError:
        logger.debug("Could not list crash dir", exc_info=True)


def _unique_filepath(crash_dir: str, timestamp: str) -> str:
    """Collision-proof path: microsecond timestamp + PID, exclusive create.

    Retries with a counter suffix when the "x" open reports the name is
    taken (same microsecond, same process — e.g. a crash cascade).
    """
    pid = os.getpid()
    candidate = os.path.join(crash_dir, f"crash_{timestamp}_{pid}.log")
    for attempt in range(100):
        if attempt:
            candidate = os.path.join(
                crash_dir, f"crash_{timestamp}_{pid}_{attempt}.log"
            )
        try:
            fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
            return candidate
        except FileExistsError:
            continue
        except OSError:
            logger.debug("Could not reserve crash file", exc_info=True)
            return candidate
    return candidate


def record_crash(exc: BaseException, context: str = "") -> str | None:
    """Write a crash log; return its path, or None when nothing was saved.

    The original exception object is preserved (never re-synthesized from
    its message) so chained causes and tracebacks survive. Callers use the
    return: None means "log this failure elsewhere, nothing hit disk".
    """
    if not _ensure_crash_dir():
        return None

    crash_dir = _get_crash_dir()
    timestamp = datetime.datetime.now(datetime.UTC).strftime(
        "%Y%m%d_%H%M%S_%f"
    )
    filepath = _unique_filepath(crash_dir, timestamp)

    try:
        from core.constants import APP_VERSION
    except Exception:
        APP_VERSION = "unknown"

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(
                f"Timestamp: {datetime.datetime.now(datetime.UTC).isoformat()}\n"
            )
            f.write(f"Context: {context}\n")
            f.write(
                f"App: KTV Player {APP_VERSION} | "
                f"Python {platform.python_version()} | "
                f"Platform {platform.platform()}\n"
            )
            f.write(f"Exception: {type(exc).__name__}: {exc}\n\n")
            f.write("Traceback:\n")
            f.write("".join(traceback.format_exception(exc)))
    except OSError:
        logger.debug("Could not write crash log", exc_info=True)
        return None

    # Post-write cleanup: count is bounded at MAX (the old code ran before
    # the write, leaving MAX+1 on disk).
    _cleanup_old_crashes()
    return filepath


_installed = False


def install_crash_handler(page_obj) -> None:
    """Route Flet page errors to disk; idempotent across re-installs."""
    global _installed
    if _installed:
        return
    _installed = True
    original_on_error = getattr(page_obj, "on_error", None)

    def crash_handler(e):
        try:
            err_msg = str(e.data) if hasattr(e, "data") else str(e)
            # Preserve the page error text; a bare message has no traceback
            # to keep, and synthesizing one would point at this frame.
            record_crash(Exception(err_msg), context="flet_page_error")
        except Exception:
            logger.debug("Crash handler failed", exc_info=True)
        if original_on_error:
            original_on_error(e)

    page_obj.on_error = crash_handler


def uninstall_crash_handler_for_tests() -> None:
    """Reset the install flag (unit tests only)."""
    global _installed
    _installed = False


async def report_error_async(exc: BaseException, context: str = "") -> str | None:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, record_crash, exc, context)
