"""Central logging configuration for KTV Player."""

import contextlib
import logging
import os
import sys

_configured_level: int | None = None


class _ShutdownSafeStreamHandler(logging.StreamHandler):
    """StreamHandler that swallows emit-time I/O errors.

    On Windows the console can be gone before the last shutdown logs
    flush (OSError Errno 22 printed as "--- Logging error ---"). Scoped
    here instead of the global ``logging.raiseExceptions = False``, so a
    handler bug elsewhere still surfaces during development.
    """

    def emit(self, record: logging.LogRecord) -> None:
        with contextlib.suppress(OSError, ValueError):
            super().emit(record)


def setup_logging(
    level: int = logging.INFO, *, force: bool = False
) -> None:
    """Configure the root logger with consistent format and handlers.

    Re-calling with a different level re-applies it (no-op when the
    effective level is unchanged, unless ``force=True``). Default level
    is INFO; ``KTV_LOG_LEVEL`` (DEBUG/INFO/WARNING/...) overrides it.
    """
    global _configured_level

    env_level = os.environ.get("KTV_LOG_LEVEL", "").strip().upper()
    if env_level:
        level = getattr(logging, env_level, level)

    from core.logger_handler import in_memory_log_handler

    root = logging.getLogger()

    if _configured_level == level and not force:
        return
    _configured_level = level
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stdout = next(
        (
            h
            for h in root.handlers
            if isinstance(h, _ShutdownSafeStreamHandler)
        ),
        None,
    )
    if stdout is None:
        stdout = _ShutdownSafeStreamHandler(sys.stdout)
        root.addHandler(stdout)
    stdout.setFormatter(fmt)
    stdout.setLevel(level)

    if not any(
        isinstance(h, type(in_memory_log_handler)) for h in root.handlers
    ):
        root.addHandler(in_memory_log_handler)
    in_memory_log_handler.setFormatter(fmt)
    in_memory_log_handler.setLevel(logging.DEBUG)

    logging.captureWarnings(True)

    logging.getLogger("flet").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
