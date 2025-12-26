"""
Custom exceptions and error handling decorators for Kubernetes API operations.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

from functools import wraps
from typing import Any, Callable

from kubernetes.client import ApiException


class KubernetesException(Exception):
    """Custom exception for Kubernetes client errors."""


def handle_k8s_api_exception(func) -> Callable[..., Any]:
    """Decorator to handle Kubernetes API exceptions."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except ApiException as e:
            match e.status:
                case 403:
                    error_msg = (
                        f"'Unauthorized' error when running {func.__name__}. Check RBAC permissions"
                    )
                case 404:
                    error_msg = f"'Not found' error when running {func.__name__}"
                case 409:
                    error_msg = f"'Conflict' error when running {func.__name__}"
                case _:
                    error_msg = (
                        f"Unexpected error when running {func.__name__}: "
                        f"HTTP {e.status} - {e.reason}"
                    )
            raise KubernetesException(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error when running {func.__name__}: {e}"
            raise KubernetesException(error_msg) from e

    return wrapper
