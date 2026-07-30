"""In-memory ring-buffer log handler for live Activity Terminal."""

from __future__ import annotations

import logging
from collections import deque
from typing import ClassVar


class MemoryLogHandler(logging.Handler):
    """In-memory ring-buffer log handler for live Activity Terminal."""

    _logs: ClassVar[deque[str]] = deque(maxlen=500)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            MemoryLogHandler._logs.append(msg)
        except Exception:
            pass

    @classmethod
    def get_logs(cls) -> list[str]:
        return list(cls._logs)

    @classmethod
    def clear_logs(cls) -> None:
        cls._logs.clear()


# Attach to root logger
in_memory_log_handler = MemoryLogHandler()
in_memory_log_handler.setLevel(logging.DEBUG)
in_memory_log_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"
    )
)

root_logger = logging.getLogger()
if in_memory_log_handler not in root_logger.handlers:
    root_logger.addHandler(in_memory_log_handler)
