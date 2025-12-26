"""
Notification module initialization with automatic provider registration.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

# ensure that the Slack notification is registered
import nodereaper.notification.slack
from nodereaper.notification.notification import send_notification

__all__ = ["send_notification"]
