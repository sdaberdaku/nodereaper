"""
Kubernetes client wrapper for NodeReaper.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

import logging

from kubernetes import client, config
from kubernetes.client.rest import ApiException


class KubernetesClient:
    """Wrapper for Kubernetes API operations."""

    def __init__(self) -> None:
        """Initialize Kubernetes client."""
        self.logger = logging.getLogger(__name__)

        try:
            config.load_incluster_config()
            self.logger.info("Loaded in-cluster Kubernetes config")
        except Exception:
            try:
                config.load_kube_config()
                self.logger.info("Loaded local Kubernetes config")
            except Exception as e:
                self.logger.error(f"Failed to load Kubernetes config: {e}")
                raise

        self.v1 = client.CoreV1Api()

    def list_nodes(self, label_selector: dict[str, str] | None = None) -> list[client.V1Node]:
        """
        List nodes in the cluster, optionally filtered by labels.

        Args:
            label_selector: Dictionary of label key-value pairs to filter nodes

        Returns:
            List of V1Node objects matching the criteria
        """
        try:
            # Convert label selector dict to Kubernetes label selector string
            selector_str = None
            if label_selector:
                selector_parts = [f"{key}={value}" for key, value in label_selector.items()]
                selector_str = ",".join(selector_parts)
                self.logger.debug(f"Using label selector: {selector_str}")

            nodes: list[client.V1Node] = self.v1.list_node(label_selector=selector_str)

            if label_selector:
                self.logger.info(
                    f"Found {len(nodes.items)} nodes matching label selector: {selector_str}"
                )
            else:
                self.logger.info(f"Found {len(nodes.items)} nodes (no label filtering)")

            return nodes.items
        except ApiException as e:
            self.logger.error(f"Failed to list nodes: {e}")
            raise

    def list_pods_on_node(self, node_name: str) -> list[client.V1Pod]:
        """List all pods running on a specific node."""
        try:
            pods: list[client.V1Pod] = self.v1.list_pod_for_all_namespaces(
                field_selector=f"spec.nodeName={node_name}"
            )
            return pods.items
        except ApiException as e:
            self.logger.error(f"Failed to list pods for node {node_name}: {e}")
            raise

    def delete_node(self, node_name: str) -> bool:
        """Delete a node from the cluster."""
        try:
            self.v1.delete_node(name=node_name)
            self.logger.info(f"Successfully deleted node {node_name}")
            return True
        except ApiException as e:
            self.logger.error(f"Failed to delete node {node_name}: {e}")
            return False

    def test_connectivity(self) -> bool:
        """Test connectivity to Kubernetes API."""
        try:
            self.v1.get_api_resources()
            return True
        except Exception as e:
            self.logger.error(f"Cannot connect to Kubernetes cluster: {e}")
            return False
