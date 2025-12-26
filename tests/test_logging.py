"""
Unit tests for JSON formatter, log setup, and structured logging configuration.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

import json
import logging
import sys
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import Mock, patch

import pytest

from nodereaper.logging.logging import JSONFormatter, setup_logging


class TestJSONFormatter:
    """Test JSON formatter functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.formatter = JSONFormatter()

    def test_json_formatter_basic_message(self):
        """Test JSON formatting of basic log message."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = self.formatter.format(record)
        parsed = json.loads(result)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "Test message"
        assert "timestamp" in parsed
        assert "exception" not in parsed

    def test_json_formatter_with_exception(self):
        """Test JSON formatting with exception info."""
        try:
            raise ValueError("Test exception")
        except ValueError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        result = self.formatter.format(record)
        parsed = json.loads(result)

        assert parsed["level"] == "ERROR"
        assert parsed["message"] == "Error occurred"
        assert "exception" in parsed
        assert "ValueError: Test exception" in parsed["exception"]

    def test_json_formatter_timestamp_format(self):
        """Test timestamp format in JSON output."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        with patch("nodereaper.logging.logging.datetime") as mock_datetime:
            mock_now = Mock()
            mock_now.isoformat.return_value = "2025-01-01T12:00:00.000000"
            mock_datetime.now.return_value = mock_now
            mock_datetime.timezone = timezone

            result = self.formatter.format(record)
            parsed = json.loads(result)

            assert parsed["timestamp"] == "2025-01-01T12:00:00.000000Z"
            mock_datetime.now.assert_called_once_with(timezone.utc)

    def test_json_formatter_message_with_args(self):
        """Test JSON formatting with message arguments."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message with %s and %d",
            args=("string", 42),
            exc_info=None,
        )

        result = self.formatter.format(record)
        parsed = json.loads(result)

        assert parsed["message"] == "Test message with string and 42"

    def test_json_formatter_different_log_levels(self):
        """Test JSON formatting with different log levels."""
        levels = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]

        for level_int, level_str in levels:
            record = logging.LogRecord(
                name="test.logger",
                level=level_int,
                pathname="",
                lineno=0,
                msg="Test message",
                args=(),
                exc_info=None,
            )

            result = self.formatter.format(record)
            parsed = json.loads(result)

            assert parsed["level"] == level_str


class TestLoggingSetup:
    """Test logging setup functionality."""

    def setup_method(self):
        """Set up test environment."""
        # Clear existing handlers
        logging.getLogger().handlers.clear()

    def teardown_method(self):
        """Clean up after each test."""
        # Clear handlers after each test
        logging.getLogger().handlers.clear()

    def test_setup_logging_json_format(self):
        """Test logging setup with JSON format."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            setup_logging(log_level="INFO", enable_json_logs=True)

            logger = logging.getLogger("test")
            logger.info("Test message")

            output = mock_stdout.getvalue()
            parsed = json.loads(output.strip())

            assert parsed["level"] == "INFO"
            assert parsed["message"] == "Test message"
            assert "timestamp" in parsed

    def test_setup_logging_text_format(self):
        """Test logging setup with text format."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            setup_logging(log_level="INFO", enable_json_logs=False)

            logger = logging.getLogger("test")
            logger.info("Test message")

            output = mock_stdout.getvalue()

            # Should not be JSON format
            with pytest.raises(json.JSONDecodeError):
                json.loads(output.strip())

            # Should contain the message in text format
            assert "INFO: Test message" in output

    def test_setup_logging_log_level(self):
        """Test logging setup with different log levels."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            setup_logging(log_level="WARNING", enable_json_logs=False)

            logger = logging.getLogger("test")
            logger.debug("Debug message")  # Should not appear
            logger.info("Info message")  # Should not appear
            logger.warning("Warning message")  # Should appear

            output = mock_stdout.getvalue()

            assert "Debug message" not in output
            assert "Info message" not in output
            assert "Warning message" in output

    def test_setup_logging_invalid_log_level(self):
        """Test logging setup with invalid log level."""
        with patch("sys.stdout", new_callable=StringIO):
            setup_logging(log_level="INVALID", enable_json_logs=False)

            # Should default to INFO level
            root_logger = logging.getLogger()
            assert root_logger.level == logging.INFO

    def test_setup_logging_clears_existing_handlers(self):
        """Test that setup_logging clears existing handlers."""
        # Add a handler first
        existing_handler = logging.StreamHandler()
        logging.getLogger().addHandler(existing_handler)

        initial_count = len(logging.getLogger().handlers)
        assert initial_count >= 1

        setup_logging(log_level="INFO", enable_json_logs=True)

        # Should have only one handler (the new one)
        assert len(logging.getLogger().handlers) == 1
        assert logging.getLogger().handlers[0] is not existing_handler

    @patch("nodereaper.logging.logging.LOG_LEVEL", "DEBUG")
    @patch("nodereaper.logging.logging.ENABLE_JSON_LOGS", False)
    def test_setup_logging_uses_settings_defaults(self):
        """Test that setup_logging uses settings module defaults."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            setup_logging()  # No parameters, should use settings

            logger = logging.getLogger("test")
            logger.debug("Debug message")  # Should appear with DEBUG level

            output = mock_stdout.getvalue()
            assert "Debug message" in output

            # Should be text format (not JSON)
            with pytest.raises(json.JSONDecodeError):
                json.loads(output.strip())

    def test_setup_logging_handler_configuration(self):
        """Test that handler is properly configured."""
        setup_logging(log_level="INFO", enable_json_logs=True)

        root_logger = logging.getLogger()

        # Should have exactly one handler
        assert len(root_logger.handlers) == 1

        handler = root_logger.handlers[0]

        # Should be StreamHandler writing to stdout
        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream is sys.stdout

        # Should have JSONFormatter
        assert isinstance(handler.formatter, JSONFormatter)

    def test_setup_logging_multiple_calls(self):
        """Test that multiple calls to setup_logging work correctly."""
        setup_logging(log_level="INFO", enable_json_logs=True)
        setup_logging(log_level="DEBUG", enable_json_logs=False)

        root_logger = logging.getLogger()

        # Should still have only one handler
        assert len(root_logger.handlers) == 1

        # Should have DEBUG level from second call
        assert root_logger.level == logging.DEBUG

        # Should have text formatter from second call
        handler = root_logger.handlers[0]
        assert not isinstance(handler.formatter, JSONFormatter)
