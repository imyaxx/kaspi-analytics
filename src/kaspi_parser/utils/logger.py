"""Centralised loguru setup.

Call `setup_logging(settings)` once on startup. Everywhere else in the code
just do `from loguru import logger`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from kaspi_parser.config import LoggingSettings

_CONSOLE_FMT = (
    "<green>{time:HH:mm:ss}</green> "
    "<level>{level: <7}</level> "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> "
    "<level>{message}</level>"
)

_FILE_FMT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <7} | "
    "{name}:{function}:{line} | {message}"
)


def setup_logging(settings: LoggingSettings) -> None:
    """Replace loguru's default handler with our console + file sinks."""
    logger.remove()

    # Console (pretty, coloured)
    logger.add(
        sys.stderr,
        format=_CONSOLE_FMT,
        level=settings.level,
        colorize=True,
        backtrace=True,
        diagnose=False,  # don't leak values into logs in production
    )

    # File (rotating, structured)
    log_path = Path(settings.file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_path,
        format=_FILE_FMT,
        level=settings.level,
        rotation=settings.rotation,
        retention=settings.retention,
        compression="zip",
        enqueue=True,   # thread-safe / async-safe
        backtrace=True,
        diagnose=False,
    )
