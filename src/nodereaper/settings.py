"""
Environment variable parsing and configuration management for NodeReaper.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

import os
import re
from datetime import timedelta


def _get_bool_env(key: str, default: bool) -> bool:
    """Get boolean environment variable.

    :param key: Environment variable name
    :param default: Default value if not set
    :return: Boolean value
    """
    value = os.getenv(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")


def _parse_duration(duration_str: str) -> timedelta:
    """Parse duration string like '10m', '1h', '30s' into timedelta.

    :param duration_str: Duration string (e.g., "30m", "1h", "45s")
    :return: Parsed timedelta object
    """
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


def _parse_list(list_str: str) -> list[str]:
    """Parse comma-separated string into list.

    Supports formats:
    - str1,str2,str3
    - Empty string (returns empty list)

    :param list_str: Comma-separated string
    :return: List of strings
    """

    return [f.strip() for f in list_str.split(",") if f.strip()]


def _parse_dict(dict_str: str) -> dict[str, str]:
    """Parse key=value pairs into dictionary.

    Supports formats:
    - key1=value1,key2=value2
    - Empty string (returns empty dict)

    :param dict_str: Comma-separated key=value pairs
    :return: Dictionary of key-value pairs
    """
    parsed_dict = {}
    if dict_str:
        for pair in dict_str.split(","):
            pair = pair.strip()
            if "=" in pair:
                key, value = pair.split("=", 1)
                parsed_dict[key.strip()] = value.strip()
    return parsed_dict


"""NodeReaper Settings"""
DRY_RUN = _get_bool_env("DRY_RUN", False)
NODE_MIN_AGE = _parse_duration(os.getenv("NODE_MIN_AGE", "30m"))
DELETION_TIMEOUT = _parse_duration(os.getenv("DELETION_TIMEOUT", "15m"))
UNHEALTHY_TAINTS = _parse_list(os.getenv("UNHEALTHY_TAINTS", ""))
PROTECTION_ANNOTATIONS = _parse_dict(os.getenv("PROTECTION_ANNOTATIONS", ""))
PROTECTION_LABELS = _parse_dict(os.getenv("PROTECTION_LABELS", ""))
ENABLE_FINALIZER_CLEANUP = _get_bool_env("ENABLE_FINALIZER_CLEANUP", True)
REMOVABLE_FINALIZERS = _parse_list(os.getenv("REMOVABLE_FINALIZERS", ""))
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
ENABLE_JSON_LOGS = _get_bool_env("ENABLE_JSON_LOGS", True)
NODE_LABEL_SELECTOR = os.getenv("NODE_LABEL_SELECTOR", "").strip()
CLUSTER_NAME = os.getenv("CLUSTER_NAME", "unknown")
TEST_KUBE_CONTEXT_NAME = os.getenv("TEST_KUBE_CONTEXT_NAME", "kind-nodereaper-test")
