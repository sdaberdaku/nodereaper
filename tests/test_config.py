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
        env_vars = [
            "DRY_RUN",
            "NODE_MIN_AGE",
            "FINALIZER_TIMEOUT",
            "DELETION_TIMEOUT",
            "DELETION_TAINTS",
            "PROTECTION_ANNOTATIONS",
            "PROTECTION_LABELS",
            "ENABLE_FINALIZER_CLEANUP",
            "FINALIZER_WHITELIST",
            "FINALIZER_BLACKLIST",
            "SLACK_WEBHOOK_URL",
            "LOG_LEVEL",
            "NODE_LABEL_SELECTOR",
            "CLUSTER_NAME",
        ]
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]

    def test_default_values(self):
        """Test default configuration values."""
        config = Config()

        self.assertFalse(config.dry_run)
        self.assertEqual(config.min_age, timedelta(minutes=10))
        self.assertEqual(config.finalizer_timeout, timedelta(minutes=5))
        self.assertEqual(config.deletion_timeout, timedelta(minutes=15))
        self.assertEqual(config.deletion_taints, [])
        self.assertEqual(config.protection_annotations, {})
        self.assertEqual(config.protection_labels, {})
        self.assertTrue(config.enable_finalizer_cleanup)
        self.assertEqual(config.finalizer_whitelist, [])
        self.assertEqual(config.finalizer_blacklist, [])
        self.assertIsNone(config.slack_webhook_url)
        self.assertEqual(config.log_level, "INFO")
        self.assertEqual(config.node_label_selector, {})
        self.assertEqual(config.cluster_name, "unknown")
        self.assertFalse(config.slack_enabled)

    def test_environment_variables(self):
        """Test configuration from environment variables."""
        with patch.dict(
            os.environ,
            {
                "DRY_RUN": "true",
                "NODE_MIN_AGE": "15m",
                "FINALIZER_TIMEOUT": "10m",
                "DELETION_TIMEOUT": "20m",
                "DELETION_TAINTS": "karpenter.sh/,cluster-autoscaler.kubernetes.io/",
                "PROTECTION_ANNOTATIONS": "karpenter.sh/do-not-evict=true,nodereaper.io/do-not-delete=true",
                "PROTECTION_LABELS": "karpenter.sh/do-not-evict=true,nodereaper.io/do-not-delete=true",
                "ENABLE_FINALIZER_CLEANUP": "false",
                "FINALIZER_WHITELIST": "karpenter.sh/termination,node.kubernetes.io/exclude-from-external-load-balancers",
                "FINALIZER_BLACKLIST": "critical.example.com/finalizer,important.custom.io/finalizer",
                "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test",
                "LOG_LEVEL": "DEBUG",
                "NODE_LABEL_SELECTOR": "cleanup-enabled=true",
                "CLUSTER_NAME": "test-cluster",
            },
        ):
            config = Config()

            self.assertTrue(config.dry_run)
            self.assertEqual(config.min_age, timedelta(minutes=15))
            self.assertEqual(config.finalizer_timeout, timedelta(minutes=10))
            self.assertEqual(config.deletion_timeout, timedelta(minutes=20))
            self.assertEqual(
                config.deletion_taints, ["karpenter.sh/", "cluster-autoscaler.kubernetes.io/"]
            )
            self.assertEqual(
                config.protection_annotations,
                {"karpenter.sh/do-not-evict": "true", "nodereaper.io/do-not-delete": "true"},
            )
            self.assertEqual(
                config.protection_labels,
                {"karpenter.sh/do-not-evict": "true", "nodereaper.io/do-not-delete": "true"},
            )
            self.assertFalse(config.enable_finalizer_cleanup)
            self.assertEqual(
                config.finalizer_whitelist,
                [
                    "karpenter.sh/termination",
                    "node.kubernetes.io/exclude-from-external-load-balancers",
                ],
            )
            self.assertEqual(
                config.finalizer_blacklist,
                ["critical.example.com/finalizer", "important.custom.io/finalizer"],
            )
            self.assertEqual(config.slack_webhook_url, "https://hooks.slack.com/test")
            self.assertEqual(config.log_level, "DEBUG")
            self.assertEqual(config.node_label_selector, {"cleanup-enabled": "true"})
            self.assertEqual(config.cluster_name, "test-cluster")
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

    def test_protection_annotations_parsing(self):
        """Test protection annotations parsing."""
        test_cases = [
            ("", {}),
            ("key=value", {"key": "value"}),
            ("key1=value1,key2=value2", {"key1": "value1", "key2": "value2"}),
            ("karpenter.sh/do-not-evict=true", {"karpenter.sh/do-not-evict": "true"}),
            (
                "karpenter.sh/do-not-evict=true,nodereaper.io/do-not-delete=enabled",
                {"karpenter.sh/do-not-evict": "true", "nodereaper.io/do-not-delete": "enabled"},
            ),
            ("  key = value  ", {"key": "value"}),  # Test whitespace handling
        ]

        for annotations_str, expected in test_cases:
            with patch.dict(os.environ, {"PROTECTION_ANNOTATIONS": annotations_str}):
                config = Config()
                self.assertEqual(
                    config.protection_annotations,
                    expected,
                    f"Failed for annotations: '{annotations_str}'",
                )

    def test_label_selector_environment_variable(self):
        """Test label selector from environment variable."""
        with patch.dict(os.environ, {"NODE_LABEL_SELECTOR": "cleanup-enabled=true"}):
            config = Config()
            self.assertEqual(config.node_label_selector, {"cleanup-enabled": "true"})

    def test_protection_labels_parsing(self):
        """Test protection labels parsing."""
        test_cases = [
            ("", {}),
            ("key=value", {"key": "value"}),
            ("key1=value1,key2=value2", {"key1": "value1", "key2": "value2"}),
            ("karpenter.sh/do-not-evict=true", {"karpenter.sh/do-not-evict": "true"}),
            (
                "karpenter.sh/do-not-evict=true,nodereaper.io/do-not-delete=enabled",
                {"karpenter.sh/do-not-evict": "true", "nodereaper.io/do-not-delete": "enabled"},
            ),
            ("  key = value  ", {"key": "value"}),  # Test whitespace handling
        ]

        for labels_str, expected in test_cases:
            with patch.dict(os.environ, {"PROTECTION_LABELS": labels_str}):
                config = Config()
                self.assertEqual(
                    config.protection_labels, expected, f"Failed for labels: '{labels_str}'"
                )

    def test_finalizer_list_parsing(self):
        """Test finalizer list parsing."""
        test_cases = [
            ("", []),
            ("karpenter.sh/termination", ["karpenter.sh/termination"]),
            (
                "karpenter.sh/termination,node.kubernetes.io/exclude-from-external-load-balancers",
                [
                    "karpenter.sh/termination",
                    "node.kubernetes.io/exclude-from-external-load-balancers",
                ],
            ),
            ("  finalizer1  ,  finalizer2  ", ["finalizer1", "finalizer2"]),  # Test whitespace
        ]

        for finalizer_str, expected in test_cases:
            with patch.dict(os.environ, {"FINALIZER_WHITELIST": finalizer_str}):
                config = Config()
                self.assertEqual(
                    config.finalizer_whitelist,
                    expected,
                    f"Failed for finalizer list: '{finalizer_str}'",
                )


if __name__ == "__main__":
    unittest.main()
