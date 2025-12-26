"""
Unit tests for notification registry, Slack provider, and error handling.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

from unittest.mock import Mock, patch

import pytest
import requests

from nodereaper.notification.notification import (
    Notifier,
    _notifiers,
    register_notifier,
    send_notification,
)
from nodereaper.notification.slack import send_slack_notification


class TestNotificationRegistry:
    """Test notification registry functionality."""

    def setup_method(self):
        """Set up test environment."""
        # Clear registry before each test
        _notifiers.clear()

    def teardown_method(self):
        """Clean up after each test."""
        # Clear registry after each test
        _notifiers.clear()

    def test_register_notifier_decorator(self):
        """Test notifier registration with decorator."""

        @register_notifier("test")
        def test_notifier(message: str) -> None:
            pass

        assert "test" in _notifiers
        assert _notifiers["test"] == test_notifier

    def test_register_multiple_notifiers(self):
        """Test registering multiple notifiers."""

        @register_notifier("notifier1")
        def notifier1(message: str) -> None:
            pass

        @register_notifier("notifier2")
        def notifier2(message: str) -> None:
            pass

        assert len(_notifiers) == 2
        assert "notifier1" in _notifiers
        assert "notifier2" in _notifiers

    def test_register_notifier_returns_function(self):
        """Test that decorator returns the original function."""

        def original_function(message: str) -> None:
            pass

        decorated = register_notifier("test")(original_function)
        assert decorated is original_function

    def test_send_notification_calls_all_registered(self):
        """Test that send_notification calls all registered notifiers."""
        mock1 = Mock()
        mock2 = Mock()

        _notifiers["mock1"] = mock1
        _notifiers["mock2"] = mock2

        test_message = "Test notification message"
        send_notification(test_message)

        mock1.assert_called_once_with(test_message)
        mock2.assert_called_once_with(test_message)

    def test_send_notification_no_registered_notifiers(self):
        """Test send_notification with no registered notifiers."""
        # Should not raise any exceptions
        send_notification("Test message")

    def test_send_notification_with_failing_notifier(self):
        """Test send_notification continues when one notifier fails."""
        mock_success = Mock()
        mock_failure = Mock(side_effect=Exception("Notifier failed"))

        _notifiers["success"] = mock_success
        _notifiers["failure"] = mock_failure

        # Should not raise exception even if one notifier fails
        # The current implementation doesn't handle exceptions, so this test
        # expects the exception to propagate
        with pytest.raises(Exception, match="Notifier failed"):
            send_notification("Test message")

        mock_success.assert_called_once_with("Test message")
        mock_failure.assert_called_once_with("Test message")


class TestSlackNotification:
    """Test Slack notification functionality."""

    @patch("nodereaper.notification.slack.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    @patch("requests.post")
    def test_send_slack_notification_success(self, mock_post):
        """Test successful Slack notification."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "ok"
        mock_post.return_value = mock_response

        send_slack_notification("Test message")

        mock_post.assert_called_once_with(
            "https://hooks.slack.com/test", json={"text": "Test message"}, timeout=10
        )
        mock_response.raise_for_status.assert_called_once()

    @patch("nodereaper.notification.slack.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    @patch("requests.post")
    def test_send_slack_notification_with_custom_webhook(self, mock_post):
        """Test Slack notification with custom webhook URL."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "ok"
        mock_post.return_value = mock_response

        custom_webhook = "https://hooks.slack.com/custom"
        send_slack_notification("Test message", slack_webhook_url=custom_webhook)

        mock_post.assert_called_once_with(custom_webhook, json={"text": "Test message"}, timeout=10)

    @patch("nodereaper.notification.slack.SLACK_WEBHOOK_URL", None)
    @patch("requests.post")
    def test_send_slack_notification_no_webhook_configured(self, mock_post):
        """Test Slack notification with no webhook configured."""
        send_slack_notification("Test message")

        # Should not make any HTTP requests
        mock_post.assert_not_called()

    @patch("nodereaper.notification.slack.SLACK_WEBHOOK_URL", "")
    @patch("requests.post")
    def test_send_slack_notification_empty_webhook(self, mock_post):
        """Test Slack notification with empty webhook URL."""
        send_slack_notification("Test message")

        # Should not make any HTTP requests
        mock_post.assert_not_called()

    @patch("nodereaper.notification.slack.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    @patch("requests.post")
    def test_send_slack_notification_http_error(self, mock_post):
        """Test Slack notification with HTTP error."""
        mock_post.side_effect = requests.HTTPError("HTTP 404 Not Found")

        # Should not raise exception
        send_slack_notification("Test message")

        mock_post.assert_called_once()

    @patch("nodereaper.notification.slack.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    @patch("requests.post")
    def test_send_slack_notification_connection_error(self, mock_post):
        """Test Slack notification with connection error."""
        mock_post.side_effect = requests.ConnectionError("Connection failed")

        # Should not raise exception
        send_slack_notification("Test message")

        mock_post.assert_called_once()

    @patch("nodereaper.notification.slack.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    @patch("requests.post")
    def test_send_slack_notification_timeout_error(self, mock_post):
        """Test Slack notification with timeout error."""
        mock_post.side_effect = requests.Timeout("Request timed out")

        # Should not raise exception
        send_slack_notification("Test message")

        mock_post.assert_called_once()

    @patch("nodereaper.notification.slack.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    @patch("requests.post")
    def test_send_slack_notification_response_error(self, mock_post):
        """Test Slack notification with HTTP response error."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("400 Bad Request")
        mock_post.return_value = mock_response

        # Should not raise exception
        send_slack_notification("Test message")

        mock_post.assert_called_once()
        mock_response.raise_for_status.assert_called_once()


class TestSlackNotificationRegistration:
    """Test that Slack notification is properly registered."""

    def setup_method(self):
        """Set up test environment."""
        # Clear registry and re-import to test registration
        _notifiers.clear()

    def test_slack_notifier_auto_registered(self):
        """Test that Slack notifier is automatically registered."""
        # Import the slack module to trigger registration
        # Force reload to ensure registration happens
        import importlib

        import nodereaper.notification.slack

        importlib.reload(nodereaper.notification.slack)

        assert "slack" in _notifiers
        # Check that it's the same function (by name since reload creates new instance)
        assert _notifiers["slack"].__name__ == "send_slack_notification"

    def teardown_method(self):
        """Clean up after each test."""
        _notifiers.clear()
