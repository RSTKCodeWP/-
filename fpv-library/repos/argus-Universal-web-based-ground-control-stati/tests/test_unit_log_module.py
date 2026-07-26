"""Tests for backend/log.py — structured logging setup."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.log import logger


class TestLogger:
    def test_logger_is_named_gcs(self):
        assert logger.name == "gcs"

    def test_logger_level_is_info(self):
        assert logger.level == logging.INFO

    def test_logger_has_handler(self):
        assert len(logger.handlers) >= 1

    def test_handler_is_stderr(self):
        handler = logger.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream is sys.stderr

    def test_handler_has_formatter(self):
        handler = logger.handlers[0]
        assert handler.formatter is not None
        assert "%(levelname)s" in handler.formatter._fmt

    def test_propagate_is_false(self):
        assert logger.propagate is False

    def test_logger_can_log(self):
        import io

        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(logger.handlers[0].formatter)
        logger.addHandler(handler)
        try:
            logger.warning("test-log-message-12345")
            assert "test-log-message-12345" in buf.getvalue()
        finally:
            logger.removeHandler(handler)

    def test_debug_not_shown_at_info_level(self):
        import io

        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        logger.addHandler(handler)
        try:
            logger.debug("should-not-appear")
            assert "should-not-appear" not in buf.getvalue()
        finally:
            logger.removeHandler(handler)
