"""In-memory ring-buffer log handler for live Activity Terminal.

NOTE: the handler alone does not make logs appear. Python delivers a
record to a handler only when the record's level passes the LOGGER's
level first — the root logger defaults to WARNING, so ``setup_logging``
must also lower the root level (it sets DEBUG) or debug/info lines are
dropped before this handler ever sees them.
"""

from __future__ import annotations

import logging
import threading
from collections import deque


class MemoryLogHandler(logging.Handler):
    """In-memory ring-buffer log handler for live Activity Terminal."""

    def __init__(self, maxlen: int = 500) -> None:
        super().__init__()
        self._logs: deque[str] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:
            self.handleError(record)
            return
        with self._lock:
            self._logs.append(msg)

    def get_logs(self) -> list[str]:
        """Snapshot of buffered lines (oldest first)."""
        with self._lock:
            return list(self._logs)

    def clear_logs(self) -> None:
        with self._lock:
            self._logs.clear()


# Attach to root logger
in_memory_log_handler = MemoryLogHandler()
in_memory_log_handler.setLevel(logging.DEBUG)
in_memory_log_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)

root_logger = logging.getLogger()
if not any(
    isinstance(h, MemoryLogHandler) for h in root_logger.handlers
):
    root_logger.addHandler(in_memory_log_handler)
