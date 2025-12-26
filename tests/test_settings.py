"""
Unit tests for environment variable parsing and configuration validation.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

import os
from datetime import timedelta
from unittest.mock import patch

import pytest

from nodereaper import settings


class TestDurationParsing:
    """Test duration parsing functionality."""

    def test_parse_duration_seconds(self):
        """Test parsing seconds."""
        result = settings._parse_duration("30s")
        assert result == timedelta(seconds=30)

    def test_parse_duration_minutes(self):
        """Test parsing minutes."""
        result = settings._parse_duration("15m")
        assert result == timedelta(minutes=15)

    def test_parse_duration_hours(self):
        """Test parsing hours."""
        result = settings._parse_duration("2h")
        assert result == timedelta(hours=2)

    def test_parse_duration_days(self):
        """Test parsing days."""
        result = settings._parse_duration("3d")
        assert result == timedelta(days=3)

    def test_parse_duration_invalid_format(self):
        """Test invalid duration format returns default."""
        result = settings._parse_duration("invalid")
        assert result == timedelta(minutes=10)

    def test_parse_duration_empty_string(self):
        """Test empty string returns default."""
        result = settings._parse_duration("")
        assert result == timedelta(minutes=10)

    def test_parse_duration_case_insensitive(self):
        """Test case insensitive parsing."""
        result = settings._parse_duration("30M")
        assert result == timedelta(minutes=30)


class TestListParsing:
    """Test list parsing functionality."""

    def test_parse_list_comma_separated(self):
        """Test parsing comma-separated list."""
        result = settings._parse_list("item1,item2,item3")
        assert result == ["item1", "item2", "item3"]

    def test_parse_list_with_spaces(self):
        """Test parsing list with spaces."""
        result = settings._parse_list("item1, item2 , item3")
        assert result == ["item1", "item2", "item3"]

    def test_parse_list_single_item(self):
        """Test parsing single item."""
        result = settings._parse_list("single-item")
        assert result == ["single-item"]

    def test_parse_list_empty_string(self):
        """Test parsing empty string."""
        result = settings._parse_list("")
        assert result == []

    def test_parse_list_empty_items(self):
        """Test parsing list with empty items."""
        result = settings._parse_list("item1,,item2,")
        assert result == ["item1", "item2"]


class TestDictParsing:
    """Test dictionary parsing functionality."""

    def test_parse_dict_key_value_pairs(self):
        """Test parsing key-value pairs."""
        result = settings._parse_dict("key1=value1,key2=value2")
        assert result == {"key1": "value1", "key2": "value2"}

    def test_parse_dict_with_spaces(self):
        """Test parsing with spaces."""
        result = settings._parse_dict("key1 = value1 , key2 = value2")
        assert result == {"key1": "value1", "key2": "value2"}

    def test_parse_dict_single_pair(self):
        """Test parsing single key-value pair."""
        result = settings._parse_dict("key=value")
        assert result == {"key": "value"}

    def test_parse_dict_empty_string(self):
        """Test parsing empty string."""
        result = settings._parse_dict("")
        assert result == {}

    def test_parse_dict_no_equals_sign(self):
        """Test parsing items without equals sign are ignored."""
        result = settings._parse_dict("key1=value1,invalid,key2=value2")
        assert result == {"key1": "value1", "key2": "value2"}

    def test_parse_dict_multiple_equals(self):
        """Test parsing with multiple equals signs."""
        result = settings._parse_dict("key=value=with=equals")
        assert result == {"key": "value=with=equals"}


class TestBooleanParsing:
    """Test boolean environment variable parsing."""

    def test_get_bool_env_true_values(self):
        """Test various true values."""
        true_values = ["true", "True", "TRUE", "1", "yes", "YES", "on", "ON"]
        for value in true_values:
            with patch.dict(os.environ, {"TEST_BOOL": value}):
                result = settings._get_bool_env("TEST_BOOL", False)
                assert result is True, f"Failed for value: {value}"

    def test_get_bool_env_false_values(self):
        """Test various false values."""
        false_values = ["false", "False", "FALSE", "0", "no", "NO", "off", "OFF", "invalid"]
        for value in false_values:
            with patch.dict(os.environ, {"TEST_BOOL": value}):
                result = settings._get_bool_env("TEST_BOOL", True)
                assert result is False, f"Failed for value: {value}"

    def test_get_bool_env_default_when_missing(self):
        """Test default value when environment variable is missing."""
        with patch.dict(os.environ, {}, clear=True):
            result = settings._get_bool_env("MISSING_VAR", True)
            assert result is True

            result = settings._get_bool_env("MISSING_VAR", False)
            assert result is False


class TestSettingsIntegration:
    """Test settings module integration."""

    def test_default_settings(self):
        """Test default settings values."""
        # Clear environment to test defaults
        with patch.dict(os.environ, {}, clear=True):
            # Reload settings module to get fresh defaults
            import importlib

            importlib.reload(settings)

            assert settings.DRY_RUN is False
            assert settings.NODE_MIN_AGE == timedelta(minutes=30)
            assert settings.DELETION_TIMEOUT == timedelta(minutes=15)
            assert settings.UNHEALTHY_TAINTS == []
            assert settings.PROTECTION_ANNOTATIONS == {}
            assert settings.PROTECTION_LABELS == {}
            assert settings.ENABLE_FINALIZER_CLEANUP is True
            assert settings.REMOVABLE_FINALIZERS == []
            assert settings.SLACK_WEBHOOK_URL is None
            assert settings.LOG_LEVEL == "INFO"
            assert settings.ENABLE_JSON_LOGS is True
            assert settings.NODE_LABEL_SELECTOR == ""
            assert settings.CLUSTER_NAME == "unknown"

    def test_environment_variable_override(self):
        """Test environment variable overrides."""
        env_vars = {
            "DRY_RUN": "true",
            "NODE_MIN_AGE": "45m",
            "DELETION_TIMEOUT": "20m",
            "UNHEALTHY_TAINTS": "taint1,taint2",
            "PROTECTION_ANNOTATIONS": "key1=value1,key2=value2",
            "PROTECTION_LABELS": "label1=value1",
            "ENABLE_FINALIZER_CLEANUP": "false",
            "REMOVABLE_FINALIZERS": "finalizer1,finalizer2",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test",
            "LOG_LEVEL": "DEBUG",
            "ENABLE_JSON_LOGS": "false",
            "NODE_LABEL_SELECTOR": "cleanup=enabled",
            "CLUSTER_NAME": "test-cluster",
            "TEST_KUBE_CONTEXT_NAME": "kind-test",
        }

        with patch.dict(os.environ, env_vars):
            # Reload settings module to pick up environment changes
            import importlib

            importlib.reload(settings)

            assert settings.DRY_RUN is True
            assert settings.NODE_MIN_AGE == timedelta(minutes=45)
            assert settings.DELETION_TIMEOUT == timedelta(minutes=20)
            assert settings.UNHEALTHY_TAINTS == ["taint1", "taint2"]
            assert settings.PROTECTION_ANNOTATIONS == {"key1": "value1", "key2": "value2"}
            assert settings.PROTECTION_LABELS == {"label1": "value1"}
            assert settings.ENABLE_FINALIZER_CLEANUP is False
            assert settings.REMOVABLE_FINALIZERS == ["finalizer1", "finalizer2"]
            assert settings.SLACK_WEBHOOK_URL == "https://hooks.slack.com/test"
            assert settings.LOG_LEVEL == "DEBUG"
            assert settings.ENABLE_JSON_LOGS is False
            assert settings.NODE_LABEL_SELECTOR == "cleanup=enabled"
            assert settings.CLUSTER_NAME == "test-cluster"
            assert settings.TEST_KUBE_CONTEXT_NAME == "kind-test"

    def teardown_method(self):
        """Clean up after each test."""
        # Reload settings to restore original state
        import importlib

        importlib.reload(settings)
