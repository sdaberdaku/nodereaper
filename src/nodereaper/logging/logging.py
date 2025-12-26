"""
JSON and text logging formatters with structured output support.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

import json
import logging
import sys
from datetime import datetime, timezone

from nodereaper.settings import ENABLE_JSON_LOGS, LOG_LEVEL


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        :param record: Log record to format
        :return: JSON formatted log string
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging(log_level: str = None, enable_json_logs: bool = None) -> None:
    """Configure logging with JSON or text format.

    :param log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    :param enable_json_logs: Enable JSON formatted logs
    """
    _log_level = LOG_LEVEL if log_level is None else log_level
    _enable_json_logs = ENABLE_JSON_LOGS if enable_json_logs is None else enable_json_logs
    # Clear any existing handlers
    logging.getLogger().handlers.clear()

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    # Set formatter based on configuration
    if _enable_json_logs:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            fmt="[%(asctime)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, _log_level, logging.INFO))
    root_logger.addHandler(handler)
