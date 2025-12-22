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

    def __init__(self, config=None) -> None:
        """Initialize Kubernetes client."""
        self.logger = logging.getLogger(__name__)
        self.config = config

        try:
            from kubernetes import config as k8s_config

            k8s_config.load_incluster_config()
            self.logger.info("Loaded in-cluster Kubernetes config")
        except Exception:
            try:
                from kubernetes import config as k8s_config

                k8s_config.load_kube_config()
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
        """Delete a node from the cluster with intelligent finalizer cleanup."""
        try:
            # First, try to get the node to check its state
            node = self.v1.read_node(name=node_name)

            # Check if node is already in terminating state with finalizers
            if self._should_cleanup_finalizers(node):
                self.logger.info(
                    f"Node {node_name} has been terminating too long, removing finalizers"
                )
                self._remove_stuck_finalizers(node)

            # Force delete with grace period of 0 seconds
            self.v1.delete_node(name=node_name, grace_period_seconds=0)
            self.logger.info(f"Successfully force deleted node {node_name}")
            return True

        except ApiException as e:
            self.logger.error(f"Failed to force delete node {node_name}: {e}")
            return False

    def _should_cleanup_finalizers(self, node) -> bool:
        """Check if finalizers should be cleaned up due to stuck termination."""
        # Check if aggressive cleanup is enabled
        if not self.config or not self.config.enable_finalizer_cleanup:
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
        timeout_seconds = self.config.finalizer_timeout.total_seconds() if self.config else 300
        if terminating_duration.total_seconds() > timeout_seconds:
            self.logger.warning(
                f"Node {node.metadata.name} has been terminating for "
                f"{int(terminating_duration.total_seconds())}s (timeout: {int(timeout_seconds)}s), checking finalizers"
            )

            # Check if it's safe to remove finalizers
            return self._is_safe_to_remove_finalizers(node)

        return False

    def _is_safe_to_remove_finalizers(self, node) -> bool:
        """Check if it's safe to remove finalizers based on whitelist/blacklist."""
        finalizers = node.metadata.finalizers or []

        # If whitelist is configured, only remove finalizers in the whitelist
        if self.config and self.config.finalizer_whitelist:
            for finalizer in finalizers:
                if finalizer in self.config.finalizer_whitelist:
                    self.logger.info(f"Finalizer in whitelist, will remove: {finalizer}")
                    return True
            self.logger.info("No finalizers match whitelist, keeping all")
            return False

        # If blacklist is configured, never remove finalizers in the blacklist
        if self.config and self.config.finalizer_blacklist:
            for finalizer in finalizers:
                if finalizer in self.config.finalizer_blacklist:
                    self.logger.info(f"Finalizer in blacklist, keeping: {finalizer}")
                    return False
            # If no finalizers are blacklisted, remove them
            self.logger.info("No finalizers in blacklist, will remove all")
            return True

        # No whitelist/blacklist configured - don't remove any finalizers for safety
        self.logger.info("No whitelist/blacklist configured, keeping all finalizers for safety")
        return False

    def _remove_stuck_finalizers(self, node) -> None:
        """Remove finalizers that are safe to remove."""
        finalizers_to_keep = []
        removed_finalizers = []

        for finalizer in node.metadata.finalizers or []:
            should_remove = False

            # Check whitelist first (if configured)
            if self.config and self.config.finalizer_whitelist:
                if finalizer in self.config.finalizer_whitelist:
                    should_remove = True

            # Check blacklist (if configured)
            elif self.config and self.config.finalizer_blacklist:
                if finalizer in self.config.finalizer_blacklist:
                    should_remove = False
                else:
                    # Not in blacklist, remove it
                    should_remove = True

            if should_remove:
                removed_finalizers.append(finalizer)
            else:
                finalizers_to_keep.append(finalizer)

        if removed_finalizers:
            # Patch node to remove stuck finalizers
            patch_body = {"metadata": {"finalizers": finalizers_to_keep}}
            self.v1.patch_node(name=node.metadata.name, body=patch_body)
            self.logger.info(
                f"Removed stuck finalizers from {node.metadata.name}: {removed_finalizers}"
            )

    def test_connectivity(self) -> bool:
        """Test connectivity to Kubernetes API."""
        try:
            self.v1.get_api_resources()
            return True
        except Exception as e:
            self.logger.error(f"Cannot connect to Kubernetes cluster: {e}")
            return False
