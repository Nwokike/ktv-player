"""Crash reporter — logs unhandled exceptions to disk with rotation."""

import asyncio
import datetime
import os
import traceback


def _get_crash_dir():
    """Get a writable crash log directory. Uses FLET_APP_STORAGE_DATA on Android."""
    storage_data = os.environ.get("FLET_APP_STORAGE_DATA")
    if storage_data:
        return os.path.join(storage_data, "crashes")
    # Fallback for desktop — use storage/ relative to project root
    return os.path.join("storage", "crashes")


MAX_CRASH_FILES = 10


def _ensure_crash_dir():
    try:
        os.makedirs(_get_crash_dir(), exist_ok=True)
    except OSError:
        pass


def _cleanup_old_crashes():
    crash_dir = _get_crash_dir()
    try:
        files = sorted(
            [f for f in os.listdir(crash_dir) if f.endswith(".log")],
            key=lambda f: os.path.getmtime(os.path.join(crash_dir, f)),
        )
        while len(files) > MAX_CRASH_FILES:
            os.remove(os.path.join(crash_dir, files.pop(0)))
    except OSError:
        pass


def record_crash(exc: Exception, context: str = ""):
    _ensure_crash_dir()
    _cleanup_old_crashes()

    crash_dir = _get_crash_dir()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(crash_dir, f"crash_{timestamp}.log")

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Context: {context}\n")
            f.write(f"Exception: {type(exc).__name__}: {exc}\n\n")
            f.write("Traceback:\n")
            f.write(
                "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            )
    except OSError:
        pass


def install_crash_handler(page_obj):
    original_on_error = getattr(page_obj, "on_error", None)

    def crash_handler(e):
        try:
            err_msg = str(e.data) if hasattr(e, "data") else str(e)
            record_crash(Exception(err_msg), context="flet_page_error")
        except Exception:
            pass
        if original_on_error:
            original_on_error(e)

    page_obj.on_error = crash_handler


async def report_error_async(exc: Exception, context: str = ""):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, record_crash, exc, context)
