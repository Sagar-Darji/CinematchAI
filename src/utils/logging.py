"""Logging configuration using loguru."""

import json
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

from config.settings import get_settings


def _json_sink(message):
    """Structured JSON sink — used in Docker/production so Loki can parse logs."""
    record = message.record
    log_entry = {
        "time": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": record["extra"].get("name", record["name"]),
        "message": record["message"],
        "function": record["function"],
        "line": record["line"],
    }
    if record["exception"]:
        log_entry["exception"] = str(record["exception"])
    print(json.dumps(log_entry), file=sys.stderr)  # noqa: T201


def setup_logging(
    log_file: Optional[Path] = None,
    level: Optional[str] = None,
    rotation: str = "100 MB",
    retention: str = "10 days",
) -> None:
    """
    Set up logging configuration.

    When LOG_FORMAT=json (set automatically inside Docker), emits one JSON
    object per line to stderr so Promtail/Loki can ingest structured logs.
    Otherwise falls back to the coloured human-readable format for local dev.

    Args:
        log_file: Path to log file. If None, logs only to console.
        level: Logging level. If None, uses settings.log_level.
        rotation: Log rotation policy (default: 100 MB).
        retention: Log retention policy (default: 10 days).
    """
    import os

    settings = get_settings()
    log_level = level or settings.log_level
    use_json = os.getenv("LOG_FORMAT", "").lower() == "json"

    # Remove default logger
    logger.remove()

    if use_json:
        # Structured JSON → Promtail picks this up and ships to Loki
        logger.add(_json_sink, level=log_level, colorize=False)
    else:
        # Human-readable coloured output for local development
        logger.add(
            sys.stderr,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            ),
            level=log_level,
            colorize=True,
        )

    # Always write to a rotating file as well when a path is given
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

    logger.info(f"Logging initialized at level: {log_level} (json={use_json})")


def get_logger(name: str):
    """
    Get a logger instance for a specific module.

    Args:
        name: Module name (usually __name__).

    Returns:
        Logger instance bound with the module name.
    """
    return logger.bind(name=name)


# Initialize default logging on import
setup_logging()
