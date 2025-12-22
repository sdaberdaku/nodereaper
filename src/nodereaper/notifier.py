"""
Notification system for NodeReaper.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

import logging

import requests


class SlackNotifier:
    """Handles Slack notifications for node deletions."""

    def __init__(self, webhook_url: str | None):
        """Initialize Slack notifier."""
        self.webhook_url = webhook_url
        self.logger = logging.getLogger(__name__)

    def send_notification(self, node_info: dict[str, str], reason: str) -> bool:
        """Send Slack notification about node deletion."""
        if not self.webhook_url:
            self.logger.debug("No Slack webhook configured, skipping notification")
            return True

        message = self._format_message(node_info, reason)
        payload = {
            "text": message,
            "username": "NodeReaper",
            "icon_emoji": ":wastebasket:",
        }

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            self.logger.info(f"Slack notification sent for node {node_info['name']}")
            return True
        except requests.RequestException as e:
            self.logger.error(f"Failed to send Slack notification: {e}")
            return False

    def _format_message(self, node_info: dict[str, str], reason: str) -> str:
        """Format the Slack message."""
        return (
            f"🗑️ NodeReaper deleted node: `{node_info['name']}`\n"
            f"Cluster: {node_info['cluster']}\n"
            f"Age: {node_info['age']}\n"
            f"Instance Type: {node_info['instance_type']}\n"
            f"Zone: {node_info['zone']}\n"
            f"Reason: {reason}"
        )


class NotificationManager:
    """Manages all notification channels."""

    def __init__(self, slack_webhook_url: str | None = None):
        """Initialize notification manager."""
        self.slack = SlackNotifier(slack_webhook_url)
        self.logger = logging.getLogger(__name__)

    def notify_node_deletion(self, node_info: dict[str, str], reason: str) -> None:
        """Send notifications about node deletion."""
        self.logger.info(f"Sending notifications for node {node_info['name']} deletion")

        # Send Slack notification
        self.slack.send_notification(node_info, reason)

        # Future: Add other notification channels (email, webhooks, etc.)
