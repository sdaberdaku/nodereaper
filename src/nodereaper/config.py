"""
Configuration management for NodeReaper.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

import os
import re
from datetime import timedelta
from typing import Dict


class Config:
    """Configuration class for NodeReaper."""

    def __init__(self):
        """Initialize configuration from environment variables."""
        self.dry_run = self._get_bool_env("DRY_RUN", False)
        self.min_age = self._parse_duration(os.getenv("NODE_MIN_AGE", "10m"))
        self.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.node_label_selector = self._parse_label_selector(os.getenv("NODE_LABEL_SELECTOR", ""))
        self.cluster_name = os.getenv("CLUSTER_NAME", "unknown")

    def _get_bool_env(self, key: str, default: bool) -> bool:
        """Get boolean environment variable."""
        value = os.getenv(key, str(default)).lower()
        return value in ("true", "1", "yes", "on")

    def _parse_duration(self, duration_str: str) -> timedelta:
        """Parse duration string like '10m', '1h', '30s' into timedelta."""
        match = re.match(r"^(\d+)([smhd])$", duration_str.lower())
        if not match:
            return timedelta(minutes=10)  # Default fallback

        value, unit = int(match.group(1)), match.group(2)

        if unit == "s":
            return timedelta(seconds=value)
        elif unit == "m":
            return timedelta(minutes=value)
        elif unit == "h":
            return timedelta(hours=value)
        elif unit == "d":
            return timedelta(days=value)

        return timedelta(minutes=10)  # Default fallback

    def _parse_label_selector(self, selector_str: str) -> Dict[str, str]:
        """
        Parse label selector string into dictionary.

        Supports formats:
        - key=value
        - key1=value1,key2=value2
        - Empty string (no filtering)

        Examples:
        - "node-role.kubernetes.io/worker=true"
        - "instance-type=m5.large,zone=us-west-2a"
        """
        if not selector_str.strip():
            return {}

        labels = {}
        for pair in selector_str.split(","):
            pair = pair.strip()
            if "=" in pair:
                key, value = pair.split("=", 1)
                labels[key.strip()] = value.strip()

        return labels

    @property
    def slack_enabled(self) -> bool:
        """Check if Slack notifications are enabled."""
        return bool(self.slack_webhook_url)
