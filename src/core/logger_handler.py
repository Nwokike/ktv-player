"""In-memory ring-buffer log handler for live Activity Terminal debugging."""

from __future__ import annotations

import logging
from typing import ClassVar


class MemoryLogHandler(logging.Handler):
    """In-memory ring-buffer log handler for live Activity Terminal."""

    _logs: ClassVar[list[str]] = []
    _MAX_LOGS = 300

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            MemoryLogHandler._logs.append(msg)
            if len(MemoryLogHandler._logs) > MemoryLogHandler._MAX_LOGS:
                MemoryLogHandler._logs.pop(0)
        except Exception:
            pass

    @classmethod
    def get_logs(cls) -> list[str]:
        return list(cls._logs)


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
