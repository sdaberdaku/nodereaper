"""Tests for notifier module."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from src.nodereaper.notifier import NotificationManager, SlackNotifier


class TestSlackNotifier(unittest.TestCase):
    """Test cases for SlackNotifier class."""

    def setUp(self):
        """Set up test environment."""
        self.webhook_url = "https://hooks.slack.com/test"
        self.notifier = SlackNotifier(self.webhook_url)

    def test_no_webhook_url(self):
        """Test behavior when no webhook URL is provided."""
        notifier = SlackNotifier(None)

        node_info = {
            "name": "test-node",
            "age": "15m",
            "cluster": "test-cluster",
            "instance_type": "m5.large",
            "zone": "us-west-2a",
        }
        result = notifier.send_notification(node_info, "empty")

        self.assertTrue(result)  # Should return True but not send anything

    @patch("requests.post")
    def test_successful_notification(self, mock_post):
        """Test successful Slack notification."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        node_info = {
            "name": "test-node",
            "age": "15m",
            "cluster": "test-cluster",
            "instance_type": "m5.large",
            "zone": "us-west-2a",
        }

        result = self.notifier.send_notification(node_info, "empty")

        self.assertTrue(result)
        mock_post.assert_called_once()

        # Check the payload
        call_args = mock_post.call_args
        payload = call_args[1]["json"]

        self.assertEqual(payload["username"], "NodeReaper")
        self.assertEqual(payload["icon_emoji"], ":wastebasket:")
        self.assertIn("test-node", payload["text"])
        self.assertIn("empty", payload["text"])

    @patch("requests.post")
    def test_failed_notification(self, mock_post):
        """Test failed Slack notification."""
        mock_post.side_effect = requests.RequestException("Network error")

        node_info = {
            "name": "test-node",
            "age": "15m",
            "cluster": "test-cluster",
            "instance_type": "m5.large",
            "zone": "us-west-2a",
        }
        result = self.notifier.send_notification(node_info, "empty")

        self.assertFalse(result)

    def test_format_message(self):
        """Test message formatting."""
        node_info = {
            "name": "test-node",
            "age": "15m",
            "cluster": "test-cluster",
            "instance_type": "m5.large",
            "zone": "us-west-2a",
        }

        message = self.notifier._format_message(node_info, "empty")

        self.assertIn("test-node", message)
        self.assertIn("15m", message)
        self.assertIn("test-cluster", message)
        self.assertIn("m5.large", message)
        self.assertIn("us-west-2a", message)
        self.assertIn("empty", message)
        self.assertIn("🗑️", message)

    def test_format_message_unschedulable(self):
        """Test message formatting for unschedulable nodes."""
        node_info = {
            "name": "cordoned-node",
            "age": "20m",
            "cluster": "prod-cluster",
            "instance_type": "c5.xlarge",
            "zone": "us-east-1a",
        }

        message = self.notifier._format_message(node_info, "unschedulable")

        self.assertIn("cordoned-node", message)
        self.assertIn("20m", message)
        self.assertIn("prod-cluster", message)
        self.assertIn("c5.xlarge", message)
        self.assertIn("us-east-1a", message)
        self.assertIn("unschedulable", message)
        self.assertIn("🗑️", message)

    def test_format_message_takeover(self):
        """Test message formatting for takeover deletion."""
        node_info = {
            "name": "stuck-node",
            "age": "30m",
            "cluster": "prod-cluster",
            "instance_type": "m5.2xlarge",
            "zone": "us-west-2b",
        }

        message = self.notifier._format_message(node_info, "takeover-empty")

        self.assertIn("stuck-node", message)
        self.assertIn("30m", message)
        self.assertIn("prod-cluster", message)
        self.assertIn("m5.2xlarge", message)
        self.assertIn("us-west-2b", message)
        self.assertIn("takeover-empty", message)
        self.assertIn("🗑️", message)


class TestNotificationManager(unittest.TestCase):
    """Test cases for NotificationManager class."""

    def setUp(self):
        """Set up test environment."""
        self.manager = NotificationManager("https://hooks.slack.com/test")

    @patch("src.nodereaper.notifier.SlackNotifier.send_notification")
    def test_notify_node_deletion(self, mock_slack_send):
        """Test node deletion notification."""
        mock_slack_send.return_value = True

        node_info = {
            "name": "test-node",
            "age": "15m",
            "cluster": "test-cluster",
            "instance_type": "m5.large",
            "zone": "us-west-2a",
        }

        self.manager.notify_node_deletion(node_info, "empty")

        mock_slack_send.assert_called_once_with(node_info, "empty")


if __name__ == "__main__":
    unittest.main()
