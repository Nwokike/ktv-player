"""Central logging configuration for KTV Player."""

import logging
import sys

_configured = False


def setup_logging(level: int = logging.DEBUG) -> None:
    """Configure root logger with consistent format and handlers."""
    global _configured
    if _configured:
        return
    _configured = True

    from core.logger_handler import in_memory_log_handler

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    existing_types = {type(h) for h in root.handlers}

    if logging.StreamHandler not in existing_types:
        stdout = logging.StreamHandler(sys.stdout)
        stdout.setFormatter(fmt)
        stdout.setLevel(logging.INFO)
        root.addHandler(stdout)

    if in_memory_log_handler not in root.handlers:
        in_memory_log_handler.setLevel(logging.DEBUG)
        root.addHandler(in_memory_log_handler)

    logging.captureWarnings(True)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
