"""Central logging configuration for KTV Player."""

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with consistent format and stderr for errors."""
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # INFO+ goes to stdout
    stdout = logging.StreamHandler(sys.stdout)
    stdout.setFormatter(fmt)
    stdout.setLevel(level)

    # WARNING+ also goes to stderr (visible in terminal, not captured by Flet)
    stderr = logging.StreamHandler(sys.stderr)
    stderr.setFormatter(fmt)
    stderr.setLevel(logging.WARNING)

    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(stdout)
        root.addHandler(stderr)

    # Ensure exceptions always include traceback
    logging.captureWarnings(True)
