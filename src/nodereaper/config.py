"""
Configuration management for NodeReaper.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

import os
import re
from datetime import timedelta


class Config:
    """Configuration class for NodeReaper."""

    def __init__(self):
        """Initialize configuration from environment variables."""
        self.dry_run = self._get_bool_env("DRY_RUN", False)
        self.min_age = self._parse_duration(os.getenv("NODE_MIN_AGE", "10m"))
        self.finalizer_timeout = self._parse_duration(os.getenv("FINALIZER_TIMEOUT", "5m"))
        self.deletion_timeout = self._parse_duration(os.getenv("DELETION_TIMEOUT", "15m"))
        self.deletion_taints = self._parse_finalizer_list(os.getenv("DELETION_TAINTS", ""))
        self.protection_annotations = self._parse_protection_annotations(
            os.getenv("PROTECTION_ANNOTATIONS", "")
        )
        self.protection_labels = self._parse_protection_labels(os.getenv("PROTECTION_LABELS", ""))
        self.enable_finalizer_cleanup = self._get_bool_env("ENABLE_FINALIZER_CLEANUP", True)
        self.cleanup_finalizers = self._parse_finalizer_list(os.getenv("CLEANUP_FINALIZERS", ""))
        self.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.node_label_selector = os.getenv("NODE_LABEL_SELECTOR", "").strip()
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

        match unit:
            case "s":
                return timedelta(seconds=value)
            case "m":
                return timedelta(minutes=value)
            case "h":
                return timedelta(hours=value)
            case "d":
                return timedelta(days=value)
            case _:
                return timedelta(minutes=10)  # Default fallback

    def _parse_finalizer_list(self, finalizer_str: str) -> list[str]:
        """
        Parse finalizer list string into list.

        Supports formats:
        - finalizer1,finalizer2,finalizer3
        - Empty string (no filtering)

        Examples:
        - "karpenter.sh/termination,node.kubernetes.io/exclude-from-external-load-balancers"
        - "example.com/custom-finalizer"
        """
        if not finalizer_str.strip():
            return []

        return [f.strip() for f in finalizer_str.split(",") if f.strip()]

    def _parse_protection_annotations(self, annotations_str: str) -> dict[str, str]:
        """
        Parse protection annotations string into dictionary.

        Supports formats:
        - key1=value1,key2=value2
        - Empty string (no protection)

        Examples:
        - "karpenter.sh/do-not-evict=true,nodereaper.io/do-not-delete=true"
        """
        if not annotations_str.strip():
            return {}

        annotations = {}
        for pair in annotations_str.split(","):
            pair = pair.strip()
            if "=" in pair:
                key, value = pair.split("=", 1)
                annotations[key.strip()] = value.strip()

        return annotations

    def _parse_protection_labels(self, labels_str: str) -> dict[str, str]:
        """
        Parse protection labels string into dictionary.

        Supports formats:
        - key1=value1,key2=value2
        - Empty string (no protection)

        Examples:
        - "karpenter.sh/do-not-evict=true,nodereaper.io/do-not-delete=true"
        """
        if not labels_str.strip():
            return {}

        labels = {}
        for pair in labels_str.split(","):
            pair = pair.strip()
            if "=" in pair:
                key, value = pair.split("=", 1)
                labels[key.strip()] = value.strip()

        return labels

    @property
    def slack_enabled(self) -> bool:
        """Check if Slack notifications are enabled."""
        return bool(self.slack_webhook_url)
