"""Central logging configuration for KTV Player."""

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with a consistent format and handler."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        ),
    )
    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers if called multiple times
    if not root.handlers:
        root.addHandler(handler)
