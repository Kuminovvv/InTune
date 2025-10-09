"""Logging configuration for the assistant."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

try:  # pragma: no cover - optional dependency
    from loguru import logger as _loguru_logger
except ModuleNotFoundError:  # pragma: no cover - executed when loguru missing
    _loguru_logger = None


if _loguru_logger is not None:
    logger = _loguru_logger
else:
    logger = logging.getLogger("intune")


def _configure_standard_logging(log_path: Optional[Path] = None) -> None:
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)


def _configure_loguru(log_path: Optional[Path] = None) -> None:
    assert _loguru_logger is not None
    _loguru_logger.remove()
    _loguru_logger.add(
        sink=lambda msg: print(msg, end=""),
        level="INFO",
        colorize=True,
        backtrace=False,
        diagnose=False,
    )
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        _loguru_logger.add(log_path, level="DEBUG", rotation="5 MB", retention=5)


def configure_logging(log_path: Optional[Path] = None) -> None:
    """Configure logging with loguru when available, otherwise use stdlib."""

    if _loguru_logger is not None:
        _configure_loguru(log_path)
    else:
        _configure_standard_logging(log_path)


__all__ = ["configure_logging", "logger"]
