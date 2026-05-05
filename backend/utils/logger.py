"""
ClassPulse AI — Logging Configuration

Structured, coloured console logging with optional file handler.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


COLOURS = {
    "DEBUG": "\033[36m",     # cyan
    "INFO": "\033[32m",      # green
    "WARNING": "\033[33m",   # yellow
    "ERROR": "\033[31m",     # red
    "CRITICAL": "\033[41m",  # red bg
}
RESET = "\033[0m"


class ColouredFormatter(logging.Formatter):
    """Console formatter with ANSI colours."""

    def format(self, record: logging.LogRecord) -> str:
        colour = COLOURS.get(record.levelname, "")
        record.levelname = f"{colour}{record.levelname:<8}{RESET}"
        return super().format(record)


def setup_logging(
    level: str = "INFO",
    log_file: str | None = None,
) -> None:
    """
    Configure root logger with console (coloured) and optional file handler.

    Args:
        level: logging level name (DEBUG, INFO, WARNING, ERROR)
        log_file: optional file path for persistent logs
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(ColouredFormatter(
        fmt="%(asctime)s │ %(levelname)s │ %(name)-28s │ %(message)s",
        datefmt="%H:%M:%S",
    ))
    root.addHandler(console)

    # File handler
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(path), encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root.addHandler(file_handler)

    # Quieten noisy libraries
    for lib in ("httpx", "httpcore", "urllib3", "PIL", "matplotlib"):
        logging.getLogger(lib).setLevel(logging.WARNING)

    logging.info("Logging configured — level=%s  file=%s", level, log_file or "none")
