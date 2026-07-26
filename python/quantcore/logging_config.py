"""Centralized logging configuration for QuantCore.

Usage:
    from quantcore.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("Engine started")
    logger.warning("Rate limit approaching")
    logger.error("Connection failed")

For web modules (imported by FastAPI/uvicorn):
    from python.quantcore.logging_config import get_logger
    logger = get_logger(__name__)

Levels:
    DEBUG   - High-frequency operational detail (per-request fetches, cache hits)
    INFO    - Normal operations (fills, daemon lifecycle, reseed events)
    WARNING - Degraded operation (rate limits, stale data, fallbacks)
    ERROR   - Failures (DB errors, network errors, rejected orders)
"""
import logging
import sys
import os

_CONFIGURED = False

def setup_logging(level: str = "INFO", log_file: str = None):
    """Configure root logging. Call once at application entry point."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_fmt)

    # Root logger
    root = logging.getLogger()
    root.setLevel(numeric_level)
    root.addHandler(console_handler)

    # Optional file handler
    if log_file:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_fmt)
        root.addHandler(file_handler)

    # Quiet noisy third-party loggers
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("feedparser").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger. Ensures logging is configured."""
    if not _CONFIGURED:
        setup_logging()
    # Strip 'python.quantcore.' prefix for cleaner output
    short_name = name.replace("python.quantcore.", "").replace("web.backend.", "web.")
    return logging.getLogger(short_name)
