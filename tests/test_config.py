"""Tests for configuration module."""

import os
import unittest
from datetime import timedelta
from unittest.mock import patch

from src.nodereaper.config import Config


class TestConfig(unittest.TestCase):
    """Test cases for Config class."""

    def setUp(self):
        """Set up test environment."""
        # Clear environment variables
        env_vars = ["DRY_RUN", "NODE_MIN_AGE", "SLACK_WEBHOOK_URL", "LOG_LEVEL"]
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]

    def test_default_values(self):
        """Test default configuration values."""
        config = Config()

        self.assertFalse(config.dry_run)
        self.assertEqual(config.min_age, timedelta(minutes=10))
        self.assertIsNone(config.slack_webhook_url)
        self.assertEqual(config.log_level, "INFO")
        self.assertFalse(config.slack_enabled)

    def test_environment_variables(self):
        """Test configuration from environment variables."""
        with patch.dict(
            os.environ,
            {
                "DRY_RUN": "true",
                "NODE_MIN_AGE": "15m",
                "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test",
                "LOG_LEVEL": "DEBUG",
            },
        ):
            config = Config()

            self.assertTrue(config.dry_run)
            self.assertEqual(config.min_age, timedelta(minutes=15))
            self.assertEqual(config.slack_webhook_url, "https://hooks.slack.com/test")
            self.assertEqual(config.log_level, "DEBUG")
            self.assertTrue(config.slack_enabled)

    def test_bool_env_parsing(self):
        """Test boolean environment variable parsing."""
        test_cases = [
            ("true", True),
            ("True", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("False", False),
            ("0", False),
            ("no", False),
            ("off", False),
            ("invalid", False),
        ]

        for value, expected in test_cases:
            with patch.dict(os.environ, {"DRY_RUN": value}):
                config = Config()
                self.assertEqual(config.dry_run, expected, f"Failed for value: {value}")

    def test_duration_parsing(self):
        """Test duration string parsing."""
        test_cases = [
            ("30s", timedelta(seconds=30)),
            ("5m", timedelta(minutes=5)),
            ("2h", timedelta(hours=2)),
            ("1d", timedelta(days=1)),
            ("invalid", timedelta(minutes=10)),  # Default fallback
            ("", timedelta(minutes=10)),  # Default fallback
        ]

        for duration_str, expected in test_cases:
            with patch.dict(os.environ, {"NODE_MIN_AGE": duration_str}):
                config = Config()
                self.assertEqual(config.min_age, expected, f"Failed for duration: {duration_str}")

    def test_label_selector_parsing(self):
        """Test node label selector parsing."""
        test_cases = [
            ("", {}),
            ("key=value", {"key": "value"}),
            ("key1=value1,key2=value2", {"key1": "value1", "key2": "value2"}),
            ("cleanup-enabled=true", {"cleanup-enabled": "true"}),
            (
                "instance-type=m5.large,zone=us-west-2a",
                {"instance-type": "m5.large", "zone": "us-west-2a"},
            ),
            ("  key = value  ", {"key": "value"}),  # Test whitespace handling
        ]

        for selector_str, expected in test_cases:
            with patch.dict(os.environ, {"NODE_LABEL_SELECTOR": selector_str}):
                config = Config()
                self.assertEqual(
                    config.node_label_selector, expected, f"Failed for selector: '{selector_str}'"
                )

    def test_label_selector_environment_variable(self):
        """Test label selector from environment variable."""
        with patch.dict(os.environ, {"NODE_LABEL_SELECTOR": "cleanup-enabled=true"}):
            config = Config()
            self.assertEqual(config.node_label_selector, {"cleanup-enabled": "true"})


if __name__ == "__main__":
    unittest.main()
