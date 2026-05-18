import asyncio
import datetime
import os
import traceback

_STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage")
CRASH_LOG_DIR = os.path.join(_STORAGE_DIR, "crashes")
MAX_CRASH_FILES = 10


def _ensure_crash_dir():
    os.makedirs(CRASH_LOG_DIR, exist_ok=True)


def _cleanup_old_crashes():
    try:
        files = sorted(
            [f for f in os.listdir(CRASH_LOG_DIR) if f.endswith(".log")],
            key=lambda f: os.path.getmtime(os.path.join(CRASH_LOG_DIR, f)),
        )
        while len(files) > MAX_CRASH_FILES:
            os.remove(os.path.join(CRASH_LOG_DIR, files.pop(0)))
    except OSError:
        pass


def record_crash(exc: Exception, context: str = ""):
    _ensure_crash_dir()
    _cleanup_old_crashes()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"crash_{timestamp}.log"
    filepath = os.path.join(CRASH_LOG_DIR, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Context: {context}\n")
            f.write(f"Exception: {type(exc).__name__}: {exc}\n\n")
            f.write("Traceback:\n")
            f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
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
