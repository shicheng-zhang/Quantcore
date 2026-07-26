"""Tests for the centralized logging configuration."""
import sys
import os
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python.quantcore.logging_config import get_logger, setup_logging


def test_get_logger_returns_logger():
    """get_logger returns a standard Python Logger."""
    logger = get_logger("test.module")
    assert isinstance(logger, logging.Logger)


def test_get_logger_strips_prefix():
    """get_logger strips python.quantcore prefix for cleaner output."""
    logger = get_logger("python.quantcore.research.backtester")
    assert logger.name == "research.backtester"


def test_setup_logging_idempotent():
    """Calling setup_logging twice doesn't add duplicate handlers."""
    setup_logging()
    root = logging.getLogger()
    handler_count = len(root.handlers)
    setup_logging()
    assert len(root.handlers) == handler_count
