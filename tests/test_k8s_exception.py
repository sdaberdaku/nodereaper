"""
Unit tests for custom exceptions and Kubernetes API error handling decorators.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

from unittest.mock import Mock

import pytest
from kubernetes.client import ApiException

from nodereaper.k8s.exception import KubernetesException, handle_k8s_api_exception


class TestKubernetesException:
    """Test KubernetesException class."""

    def test_kubernetes_exception_creation(self):
        """Test creating KubernetesException."""
        message = "Test error message"
        exception = KubernetesException(message)

        assert str(exception) == message
        assert isinstance(exception, Exception)

    def test_kubernetes_exception_with_cause(self):
        """Test KubernetesException with cause."""
        original_error = ValueError("Original error")
        message = "Kubernetes error"

        exception = KubernetesException(message)
        exception.__cause__ = original_error

        assert str(exception) == message
        assert exception.__cause__ is original_error


class TestHandleK8sApiExceptionDecorator:
    """Test handle_k8s_api_exception decorator."""

    def test_decorator_success_case(self):
        """Test decorator with successful function execution."""

        @handle_k8s_api_exception
        def successful_function(value):
            return value * 2

        result = successful_function(5)
        assert result == 10

    def test_decorator_api_exception_403(self):
        """Test decorator handling 403 Forbidden error."""

        @handle_k8s_api_exception
        def function_with_403():
            raise ApiException(status=403, reason="Forbidden")

        with pytest.raises(KubernetesException) as exc_info:
            function_with_403()

        assert "'Unauthorized' error when running function_with_403. Check RBAC permissions" in str(
            exc_info.value
        )
        assert isinstance(exc_info.value.__cause__, ApiException)

    def test_decorator_api_exception_404(self):
        """Test decorator handling 404 Not Found error."""

        @handle_k8s_api_exception
        def function_with_404():
            raise ApiException(status=404, reason="Not Found")

        with pytest.raises(KubernetesException) as exc_info:
            function_with_404()

        assert "'Not found' error when running function_with_404" in str(exc_info.value)

    def test_decorator_api_exception_409(self):
        """Test decorator handling 409 Conflict error."""

        @handle_k8s_api_exception
        def function_with_409():
            raise ApiException(status=409, reason="Conflict")

        with pytest.raises(KubernetesException) as exc_info:
            function_with_409()

        assert "'Conflict' error when running function_with_409" in str(exc_info.value)

    def test_decorator_api_exception_other_status(self):
        """Test decorator handling other HTTP status codes."""

        @handle_k8s_api_exception
        def function_with_500():
            raise ApiException(status=500, reason="Internal Server Error")

        with pytest.raises(KubernetesException) as exc_info:
            function_with_500()

        expected_msg = (
            "Unexpected error when running function_with_500: HTTP 500 - Internal Server Error"
        )
        assert expected_msg in str(exc_info.value)

    def test_decorator_generic_exception(self):
        """Test decorator handling generic exceptions."""

        @handle_k8s_api_exception
        def function_with_generic_error():
            raise ValueError("Generic error")

        with pytest.raises(KubernetesException) as exc_info:
            function_with_generic_error()

        assert "Unexpected error when running function_with_generic_error: Generic error" in str(
            exc_info.value
        )
        assert isinstance(exc_info.value.__cause__, ValueError)

    def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves function metadata."""

        @handle_k8s_api_exception
        def test_function():
            """Test function docstring."""
            pass

        assert test_function.__name__ == "test_function"
        assert test_function.__doc__ == "Test function docstring."

    def test_decorator_with_arguments_and_kwargs(self):
        """Test decorator with function that has arguments and kwargs."""

        @handle_k8s_api_exception
        def function_with_args(arg1, arg2, kwarg1=None, kwarg2=None):
            return f"{arg1}-{arg2}-{kwarg1}-{kwarg2}"

        result = function_with_args("a", "b", kwarg1="c", kwarg2="d")
        assert result == "a-b-c-d"

    def test_decorator_exception_chaining(self):
        """Test that original exception is properly chained."""
        original_exception = ApiException(status=403, reason="Forbidden")

        @handle_k8s_api_exception
        def function_with_chained_exception():
            raise original_exception

        with pytest.raises(KubernetesException) as exc_info:
            function_with_chained_exception()

        # Check that the original exception is chained
        assert exc_info.value.__cause__ is original_exception

    def test_decorator_multiple_decorators(self):
        """Test decorator works with other decorators."""

        def another_decorator(func):
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        @another_decorator
        @handle_k8s_api_exception
        def decorated_function():
            return "success"

        result = decorated_function()
        assert result == "success"

    def test_decorator_api_exception_without_reason(self):
        """Test decorator handling ApiException without reason."""

        @handle_k8s_api_exception
        def function_with_no_reason():
            exception = ApiException(status=500)
            exception.reason = None
            raise exception

        with pytest.raises(KubernetesException) as exc_info:
            function_with_no_reason()

        assert "HTTP 500 - None" in str(exc_info.value)

    def test_decorator_api_exception_with_body(self):
        """Test decorator handling ApiException with response body."""

        @handle_k8s_api_exception
        def function_with_body():
            exception = ApiException(status=400, reason="Bad Request")
            exception.body = '{"message": "Invalid request"}'
            raise exception

        with pytest.raises(KubernetesException) as exc_info:
            function_with_body()

        assert "HTTP 400 - Bad Request" in str(exc_info.value)
