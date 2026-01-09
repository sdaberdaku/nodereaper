"""
Prometheus client for querying node empty duration metrics.

SPDX-License-Identifier: Apache-2.0
Copyright 2026 Sebastian Daberdaku
"""

import logging
from datetime import timedelta
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

from nodereaper.settings import (
    PROMETHEUS_MIN_EMPTY_DURATION,
    PROMETHEUS_PASSWORD,
    PROMETHEUS_TIMEOUT,
    PROMETHEUS_URL,
    PROMETHEUS_USERNAME,
)

logger = logging.getLogger(__name__)


class PrometheusClient:
    """Client for querying Prometheus metrics to determine node empty duration."""

    def __init__(
        self,
        url: str = None,
        username: str = None,
        password: str = None,
        min_empty_duration: timedelta = None,
        timeout: timedelta = None,
    ) -> None:
        """Initialize Prometheus client.

        :param url: Prometheus server URL
        :param username: Basic auth username (optional)
        :param password: Basic auth password (optional)
        :param timeout: Request timeout duration
        """

        self.url = (url or PROMETHEUS_URL).rstrip("/")
        self.username = username or PROMETHEUS_USERNAME
        self.password = password or PROMETHEUS_PASSWORD
        self.min_empty_duration = (
            PROMETHEUS_MIN_EMPTY_DURATION if min_empty_duration is None else min_empty_duration
        )
        self.timeout = PROMETHEUS_TIMEOUT if timeout is None else timeout

        self.session = requests.Session()
        if self.username and self.password:
            self.session.auth = HTTPBasicAuth(self.username, self.password)

        logger.info(f"Prometheus client initialized with URL: {self.url}")

    def get_non_empty_nodes(self) -> set[str]:
        """
        Return set of nodes that had non-DaemonSet Pods in the last `self.min_empty_duration`.
        This runs one query and returns a set of node names.

        :return: Set of node names with non-DaemonSet Pods.
        """

        # This query returns values only for non-empty nodes
        query = (
            f"max_over_time("
            f'(count by (node) (kube_pod_info{{created_by_kind!="DaemonSet"}})'
            f")[{self.min_empty_duration.total_seconds()}s:])"
        )

        response = self._run_query(query)
        result: list[dict] = response.get("data", {}).get("result", [])
        nonempty_nodes: set[str | None] = {
            series.get("metric", {}).get("node") for series in result
        }
        # Filter out empty node names (non-scheduled Pods may return empty node label)
        return {node for node in nonempty_nodes if node}

    def is_server_available(self) -> bool:
        """
        Check if Prometheus server is available.

        :return: True if Prometheus is reachable and responding, False otherwise.
        """
        response = self.session.get(
            f"{self.url}/api/v1/query",
            params={"query": "up"},
            timeout=self.timeout.total_seconds(),
        )
        return response.ok

    def _run_query(self, query: str) -> dict[str, Any]:
        """
        Execute a Prometheus query.

        :param query: PromQL query string.
        :return: Query response data.
        """
        try:
            response = self.session.get(
                f"{self.url}/api/v1/query",
                params={"query": query},
                timeout=self.timeout.total_seconds(),
            )
            response.raise_for_status()

            data: dict[str, Any] = response.json()
            if data.get("status") != "success":
                logger.error(
                    "Prometheus query failed: %s",
                    data.get("error", "Unknown error"),
                )
                return {}

            return data
        except requests.exceptions.RequestException:
            logger.exception("Prometheus query request failed!")
            return {}
