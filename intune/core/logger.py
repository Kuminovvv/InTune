"""Logging configuration for the assistant."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from loguru import logger


def configure_logging(log_path: Optional[Path] = None) -> None:
    """Configure loguru logger with sane defaults."""

    logger.remove()
    logger.add(
        sink=lambda msg: print(msg, end=""),
        level="INFO",
        colorize=True,
        backtrace=False,
        diagnose=False,
    )
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(log_path, level="DEBUG", rotation="5 MB", retention=5)


__all__ = ["configure_logging", "logger"]
