"""
Unit tests for Prometheus client functionality.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

import json
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
import requests

from nodereaper.k8s.prometheus import PrometheusClient


class TestPrometheusClient:
    """Test cases for PrometheusClient."""

    def test_init_without_auth(self):
        """Test client initialization without authentication."""
        client = PrometheusClient("http://prometheus:9090")
        assert client.url == "http://prometheus:9090"
        assert client.session.auth is None
        assert client.timeout == timedelta(seconds=30)

    def test_init_with_none_credentials(self):
        """Test client initialization with None credentials (no auth)."""
        client = PrometheusClient(
            "http://prometheus:9090",
            username=None,
            password=None,
        )
        assert client.url == "http://prometheus:9090"
        assert client.session.auth is None
        assert client.timeout == timedelta(seconds=30)

    def test_init_with_empty_credentials(self):
        """Test client initialization with empty string credentials (no auth)."""
        client = PrometheusClient(
            "http://prometheus:9090",
            username="",
            password="",
        )
        assert client.url == "http://prometheus:9090"
        assert client.session.auth is None
        assert client.timeout == timedelta(seconds=30)

    def test_init_with_auth(self):
        """Test client initialization with authentication."""
        client = PrometheusClient(
            "http://prometheus:9090",
            username="user",
            password="pass",
            timeout=timedelta(seconds=60),
        )
        assert client.url == "http://prometheus:9090"
        assert client.session.auth is not None
        assert client.timeout == timedelta(seconds=60)

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped from URL."""
        client = PrometheusClient("http://prometheus:9090/")
        assert client.url == "http://prometheus:9090"

    @patch("requests.Session.get")
    def test_is_available_success(self, mock_get):
        """Test successful availability check."""
        mock_response = Mock()
        mock_response.ok = True
        mock_get.return_value = mock_response

        client = PrometheusClient("http://prometheus:9090")
        assert client.is_server_available() is True

        mock_get.assert_called_once_with(
            "http://prometheus:9090/api/v1/query",
            params={"query": "up"},
            timeout=30.0,
        )

    @patch("requests.Session.get")
    def test_is_available_failure(self, mock_get):
        """Test failed availability check."""
        mock_get.side_effect = requests.exceptions.RequestException("Connection failed")

        client = PrometheusClient("http://prometheus:9090")
        # The method should catch the exception and return False
        with pytest.raises(requests.exceptions.RequestException):
            client.is_server_available()

    @patch("requests.Session.get")
    def test_is_available_non_200_status(self, mock_get):
        """Test availability check with non-200 status."""
        mock_response = Mock()
        mock_response.ok = False
        mock_get.return_value = mock_response

        client = PrometheusClient("http://prometheus:9090")
        assert client.is_server_available() is False

    @patch("requests.Session.get")
    def test_query_success(self, mock_get):
        """Test successful Prometheus query."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {"result": [{"value": [1640995200, "1"]}]},
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = PrometheusClient("http://prometheus:9090")
        result = client._run_query("up")

        assert result is not None
        assert result["status"] == "success"
        mock_get.assert_called_once_with(
            "http://prometheus:9090/api/v1/query",
            params={"query": "up"},
            timeout=30.0,
        )

    @patch("requests.Session.get")
    def test_query_prometheus_error(self, mock_get):
        """Test Prometheus query with error response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "error",
            "error": "invalid query",
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = PrometheusClient("http://prometheus:9090")
        result = client._run_query("invalid_query")

        assert result == {}

    @patch("requests.Session.get")
    def test_query_request_exception(self, mock_get):
        """Test Prometheus query with request exception."""
        mock_get.side_effect = requests.exceptions.RequestException("Connection failed")

        client = PrometheusClient("http://prometheus:9090")
        result = client._run_query("up")

        assert result == {}

    @patch("requests.Session.get")
    def test_query_http_error(self, mock_get):
        """Test Prometheus query with HTTP error."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404")
        mock_get.return_value = mock_response

        client = PrometheusClient("http://prometheus:9090")
        result = client._run_query("up")

        assert result == {}

    @patch("requests.Session.get")
    def test_query_json_decode_error(self, mock_get):
        """Test Prometheus query with JSON decode error."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = PrometheusClient("http://prometheus:9090")

        # The method should let the JSON decode error bubble up
        with pytest.raises(json.JSONDecodeError):
            client._run_query("up")

    @patch("requests.Session.get")
    def test_get_non_empty_nodes_success(self, mock_get):
        """Test successful non-empty nodes query."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "result": [
                    {"metric": {"node": "node-1"}},
                    {"metric": {"node": "node-2"}},
                ]
            },
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = PrometheusClient(
            "http://prometheus:9090", min_empty_duration=timedelta(minutes=10)
        )
        nodes = client.get_non_empty_nodes()

        assert nodes == {"node-1", "node-2"}

        expected_query = (
            "max_over_time("
            '(count by (node) (kube_pod_info{created_by_kind!="DaemonSet"}))'
            "[600s:])"
        )
        mock_get.assert_called_once_with(
            "http://prometheus:9090/api/v1/query",
            params={"query": expected_query},
            timeout=30.0,
        )

    @patch("requests.Session.get")
    def test_get_non_empty_nodes_no_data(self, mock_get):
        """Test non-empty nodes query with no data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {"result": []},
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = PrometheusClient("http://prometheus:9090")
        nodes = client.get_non_empty_nodes()

        assert nodes == set()

    @patch("requests.Session.get")
    def test_get_non_empty_nodes_query_failure(self, mock_get):
        """Test non-empty nodes query failure."""
        mock_get.side_effect = requests.exceptions.RequestException("Connection failed")

        client = PrometheusClient("http://prometheus:9090")
        nodes = client.get_non_empty_nodes()

        assert nodes == set()

    @patch("requests.Session.get")
    def test_get_non_empty_nodes_filters_empty_names(self, mock_get):
        """Test that empty node names are filtered out."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "result": [
                    {"metric": {"node": "node-1"}},
                    {"metric": {"node": ""}},  # Empty node name
                    {"metric": {}},  # No node key
                    {"metric": {"node": "node-2"}},
                ]
            },
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = PrometheusClient("http://prometheus:9090")
        nodes = client.get_non_empty_nodes()

        assert nodes == {"node-1", "node-2"}
