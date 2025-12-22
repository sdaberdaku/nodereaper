"""
Node analysis logic for NodeReaper.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

"""Node analysis logic for NodeReaper."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from kubernetes import client


class NodeAnalyzer:
    """Analyzes nodes to determine if they should be deleted."""

    def __init__(self, min_age: timedelta):
        """Initialize node analyzer."""
        self.min_age = min_age
        self.logger = logging.getLogger(__name__)

    def should_delete_node(self, node: client.V1Node, pods: List[client.V1Pod]) -> Tuple[bool, str]:
        """
        Determine if a node should be deleted.

        Returns:
            Tuple of (should_delete: bool, reason: str)
        """
        node_name = node.metadata.name

        # Check node age
        if not self._is_node_old_enough(node):
            age = self._get_node_age(node)
            self.logger.debug(f"Node {node_name} is too young ({self._format_age(age)}), skipping")
            return False, ""

        # Check Karpenter markers
        if self._is_karpenter_marked(node):
            self.logger.debug(f"Node {node_name} is marked by Karpenter, skipping")
            return False, ""

        # Check if unreachable
        if self._is_node_unreachable(node):
            self.logger.info(f"Node {node_name} is unreachable, marking for deletion")
            return True, "unreachable"

        # Check if unschedulable (cordoned)
        if self._is_node_unschedulable(node):
            self.logger.info(f"Node {node_name} is unschedulable, marking for deletion")
            return True, "unschedulable"

        # Check if empty
        if self._is_node_empty(pods):
            self.logger.info(f"Node {node_name} is empty, marking for deletion")
            return True, "empty"

        self.logger.debug(f"Node {node_name} has workloads, keeping")
        return False, ""

    def _is_node_old_enough(self, node: client.V1Node) -> bool:
        """Check if node is old enough to be deleted."""
        age = self._get_node_age(node)
        return age >= self.min_age

    def _get_node_age(self, node: client.V1Node) -> timedelta:
        """Get the age of a node."""
        creation_time: datetime = node.metadata.creation_timestamp
        return datetime.now(timezone.utc) - creation_time

    def _format_age(self, age: timedelta) -> str:
        """Format timedelta into human readable string."""
        total_seconds = int(age.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            return f"{total_seconds // 60}m"
        elif total_seconds < 86400:
            return f"{total_seconds // 3600}h"
        else:
            return f"{total_seconds // 86400}d"

    def _is_karpenter_marked(self, node: client.V1Node) -> bool:
        """Check if node is marked for deletion by Karpenter."""
        # Check annotations
        annotations = node.metadata.annotations or {}
        if any(key.startswith("karpenter.sh/") for key in annotations.keys()):
            if "karpenter.sh/do-not-evict" in annotations:
                return True

        # Check taints
        taints = node.spec.taints or []
        for taint in taints:
            if "karpenter.sh" in taint.key and taint.effect == "NoSchedule":
                return True

        return False

    def _is_node_unreachable(self, node: client.V1Node) -> bool:
        """Check if node is in unreachable state."""
        conditions = node.status.conditions or []
        for condition in conditions:
            if condition.type == "Ready" and condition.status == "Unknown":
                return True
        return False

    def _is_node_unschedulable(self, node: client.V1Node) -> bool:
        """Check if node has unschedulable taint (cordoned)."""
        taints = node.spec.taints or []
        for taint in taints:
            if taint.key == "node.kubernetes.io/unschedulable" and taint.effect == "NoSchedule":
                return True
        return False

    def _is_node_empty(self, pods: List[client.V1Pod]) -> bool:
        """Check if node only has DaemonSet pods running."""
        non_daemonset_pods = 0
        for pod in pods:
            if not self._is_daemonset_pod(pod):
                non_daemonset_pods += 1
                self.logger.debug(f"Found non-DaemonSet pod {pod.metadata.name}")

        return non_daemonset_pods == 0

    def _is_daemonset_pod(self, pod: client.V1Pod) -> bool:
        """Check if pod is owned by a DaemonSet."""
        owner_references = pod.metadata.owner_references or []
        return any(owner.kind == "DaemonSet" for owner in owner_references)

    def get_node_info(self, node: client.V1Node, cluster_name: str = "unknown") -> dict:
        """Get node information for logging/notifications."""
        labels = node.metadata.labels or {}
        age = self._get_node_age(node)

        return {
            "name": node.metadata.name,
            "age": self._format_age(age),
            "cluster": cluster_name,
            "instance_type": labels.get("node.kubernetes.io/instance-type", "unknown"),
            "zone": labels.get("topology.kubernetes.io/zone", "unknown"),
            "creation_time": node.metadata.creation_timestamp.isoformat(),
        }
