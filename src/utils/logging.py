"""Logging configuration using loguru."""

import sys
from pathlib import Path
from typing import Optional

from loguru import logger

from config.settings import get_settings


def setup_logging(
    log_file: Optional[Path] = None,
    level: Optional[str] = None,
    rotation: str = "100 MB",
    retention: str = "10 days",
) -> None:
    """
    Set up logging configuration.

    Args:
        log_file: Path to log file. If None, logs only to console.
        level: Logging level. If None, uses settings.log_level.
        rotation: Log rotation policy (default: 100 MB).
        retention: Log retention policy (default: 10 days).
    """
    settings = get_settings()
    log_level = level or settings.log_level

    # Remove default logger
    logger.remove()

    # Add console logger with formatting
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=log_level,
        colorize=True,
    )

    # Add file logger if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=log_level,
            rotation=rotation,
            retention=retention,
            compression="zip",
        )

    logger.info(f"Logging initialized at level: {log_level}")


def get_logger(name: str):
    """
    Get a logger instance for a specific module.

    Args:
        name: Module name (usually __name__).

    Returns:
        Logger instance configured for the module.
    """
    return logger.bind(name=name)


# Initialize default logging
setup_logging()
