"""
Pluggable notification system with auto-registration and provider management.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""
from typing import Any, Callable, Protocol


class Notifier(Protocol):
    """Protocol for notification functions."""

    def __call__(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Send notification message.

        :param message: Message to send
        :param args: Additional arguments
        :param kwargs: Additional keyword arguments
        """
        pass


_notifiers: dict[str, Notifier] = {}


def register_notifier(name: str) -> Callable[[Notifier], Notifier]:
    """Decorator to auto-register notifiers.

    :param name: Name of the notifier
    :return: Decorator function
    """

    def wrapper(func: Notifier) -> Notifier:
        _notifiers[name] = func
        return func

    return wrapper


def send_notification(message: str) -> None:
    """Send notifications using all registered notifiers.

    :param message: Message to send
    """
    for notifier in _notifiers.values():
        notifier(message)
