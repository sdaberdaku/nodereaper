"""
Kubernetes client wrapper for NodeReaper.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

import logging

from kubernetes import client as k8s
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException

from nodereaper.config import Config


class KubernetesClient:
    """Wrapper for Kubernetes API operations."""

    def __init__(self, config: Config | None = None) -> None:
        """Initialize Kubernetes client."""
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.config: Config | None = config

        try:
            k8s_config.load_incluster_config()
            self.logger.info("Loaded in-cluster Kubernetes config")
        except Exception:
            try:
                k8s_config.load_kube_config()
                self.logger.info("Loaded local Kubernetes config")
            except Exception as e:
                self.logger.error(f"Failed to load Kubernetes config: {e}")
                raise

        self.v1: k8s.CoreV1Api = k8s.CoreV1Api()

    def list_nodes(self, label_selector: str = "") -> list[k8s.V1Node]:
        """
        List nodes in the cluster, optionally filtered by labels.

        Args:
            label_selector: Kubernetes label selector string (e.g., "key1=value1,key2=value2")

        Returns:
            List of V1Node objects matching the criteria
        """
        try:
            selector_str: str | None = label_selector or None
            nodes: k8s.V1NodeList = self.v1.list_node(label_selector=selector_str)

            filter_msg = f" matching '{label_selector}'" if label_selector else ""
            self.logger.info(f"Found {len(nodes.items)} nodes{filter_msg}")

            return nodes.items
        except ApiException as e:
            self.logger.error(f"Failed to list nodes: {e}")
            raise

    def list_pods_on_node(self, node_name: str) -> list[k8s.V1Pod]:
        """List all pods running on a specific node."""
        try:
            pods: k8s.V1PodList = self.v1.list_pod_for_all_namespaces(
                field_selector=f"spec.nodeName={node_name}"
            )
            return pods.items
        except ApiException as e:
            self.logger.error(f"Failed to list pods for node {node_name}: {e}")
            raise

    def delete_node(self, node_name: str) -> bool:
        """Delete a node from the cluster with intelligent finalizer cleanup."""
        try:
            # First, try to get the node to check its state
            node: k8s.V1Node = self.v1.read_node(name=node_name)

            # Check if node is already in terminating state with finalizers
            if self._cleanup_stuck_finalizers(node):
                self.logger.info(
                    f"Node {node_name} has been terminating too long, removed stuck finalizers"
                )

            # Force delete with grace period of 0 seconds
            self.v1.delete_node(name=node_name, grace_period_seconds=0)
            self.logger.info(f"Successfully force deleted node {node_name}")
            return True

        except ApiException as e:
            self.logger.error(f"Failed to force delete node {node_name}: {e}")
            return False

    def _cleanup_stuck_finalizers(self, node: k8s.V1Node) -> bool:
        """
        Check if finalizers should be cleaned up and remove them if needed.

        Args:
            node: The V1Node object to check and potentially clean up

        Returns:
            True if finalizers were cleaned up, False otherwise.
        """
        # Check if aggressive cleanup is enabled
        if not self.config.enable_finalizer_cleanup:
            return False

        # Check if we have cleanup finalizers configured
        if not self.config.cleanup_finalizers:
            return False

        # Check if node is in terminating state
        if not node.metadata.deletion_timestamp:
            return False

        # Check if node has finalizers
        if not node.metadata.finalizers:
            return False

        # Calculate how long node has been terminating
        from datetime import datetime, timezone

        deletion_time = node.metadata.deletion_timestamp
        current_time = datetime.now(timezone.utc)
        terminating_duration = current_time - deletion_time

        # Use configured finalizer timeout
        timeout_seconds = self.config.finalizer_timeout.total_seconds()
        if terminating_duration.total_seconds() <= timeout_seconds:
            return False

        self.logger.warning(
            f"Node {node.metadata.name} has been terminating for "
            f"{int(terminating_duration.total_seconds())}s (timeout: {int(timeout_seconds)}s), checking finalizers"
        )

        # Separate finalizers into keep/remove lists
        finalizers_to_keep: list[str] = []
        removed_finalizers: list[str] = []

        for finalizer in node.metadata.finalizers:
            if finalizer in self.config.cleanup_finalizers:
                removed_finalizers.append(finalizer)
            else:
                finalizers_to_keep.append(finalizer)

        # Only patch if we have finalizers to remove
        if removed_finalizers:
            patch_body: dict[str, dict[str, list[str]]] = {
                "metadata": {"finalizers": finalizers_to_keep}
            }
            self.v1.patch_node(name=node.metadata.name, body=patch_body)
            self.logger.info(
                f"Removed stuck finalizers from {node.metadata.name}: {removed_finalizers}"
            )
            return True

        return False

    def test_connectivity(self) -> bool:
        """Test connectivity to Kubernetes API."""
        try:
            self.v1.get_api_resources()
            return True
        except Exception as e:
            self.logger.error(f"Cannot connect to Kubernetes cluster: {e}")
            return False
