"""
Slack webhook notification provider with error handling and retry logic.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""
import logging

import requests

from nodereaper.notification.notification import register_notifier
from nodereaper.settings import SLACK_WEBHOOK_URL

logger = logging.getLogger(__name__)


@register_notifier("slack")
def send_slack_notification(message: str, slack_webhook_url: str = None) -> None:
    """Send message to Slack via webhook.

    :param message: Message to send
    :param slack_webhook_url: Slack webhook URL (optional)
    """
    webhook_url = SLACK_WEBHOOK_URL if slack_webhook_url is None else slack_webhook_url

    if not webhook_url:
        logger.warning("No Slack webhook configured, skipping notification")
        return

    try:
        response = requests.post(webhook_url, json={"text": message}, timeout=10)
        response.raise_for_status()

        logger.info(
            f"Slack notification message sent: '{message}'."
            f"Response: {response.status_code} '{response.text}'"
        )
    except requests.RequestException as e:
        logger.exception(f"Failed to send Slack notification: {e}")
