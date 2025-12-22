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

    def __init__(
        self,
        min_age: timedelta,
        deletion_timeout: timedelta = None,
        deletion_taints: list[str] = None,
        protection_annotations: dict[str, str] = None,
        protection_labels: dict[str, str] = None,
    ):
        """Initialize node analyzer."""
        self.min_age = min_age
        self.deletion_timeout = deletion_timeout or timedelta(minutes=15)
        self.deletion_taints = deletion_taints or []
        self.protection_annotations = protection_annotations or {}
        self.protection_labels = protection_labels or {}
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

        # Check deletion markers with timeout
        marked_for_deletion, marking_age = self._is_marked_for_deletion(node)
        if marked_for_deletion:
            # If marking_age is None, it means permanent protection (no timeout)
            if marking_age is None:
                self.logger.debug(f"Node {node_name} has permanent protection annotation, skipping")
                return False, ""

            # Special case: unschedulable nodes should be deleted immediately regardless of timeout
            if self._has_unschedulable_taint(node):
                self.logger.info(
                    f"Node {node_name} is unschedulable, marking for immediate deletion"
                )
                return True, "unschedulable"

            elif marking_age < self.deletion_timeout:
                self.logger.debug(
                    f"Node {node_name} is marked for deletion for {self._format_age(marking_age)} "
                    f"(timeout: {self._format_age(self.deletion_timeout)}), skipping"
                )
                return False, ""
            else:
                self.logger.info(
                    f"Node {node_name} marked for deletion for {self._format_age(marking_age)} "
                    f"(timeout: {self._format_age(self.deletion_timeout)}), taking over deletion"
                )
                # Continue with normal deletion logic, but track that we're taking over
                taking_over_deletion = True
        else:
            taking_over_deletion = False

        # Check if unreachable
        if self._is_node_unreachable(node):
            reason = "takeover-unreachable" if taking_over_deletion else "unreachable"
            self.logger.info(f"Node {node_name} is unreachable, marking for deletion")
            return True, reason

        # Check if empty
        if self._is_node_empty(pods):
            reason = "takeover-empty" if taking_over_deletion else "empty"
            self.logger.info(f"Node {node_name} is empty, marking for deletion")
            return True, reason

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

    def _is_marked_for_deletion(self, node: client.V1Node) -> Tuple[bool, timedelta]:
        """
        Check if node is marked for deletion by any autoscaler/system.

        Returns:
            Tuple of (is_marked: bool, marking_age: timedelta or None)
        """
        annotations = node.metadata.annotations or {}
        labels = node.metadata.labels or {}

        # Check for protection annotations (always respected, no timeout)
        for protection_key, protection_value in self.protection_annotations.items():
            node_annotation_value = annotations.get(protection_key)
            if node_annotation_value == protection_value:
                self.logger.debug(
                    f"Node has protection annotation: {protection_key}={protection_value}"
                )
                return True, None  # No timeout for protection annotations

        # Check for protection labels (always respected, no timeout)
        for protection_key, protection_value in self.protection_labels.items():
            node_label_value = labels.get(protection_key)
            if node_label_value == protection_value:
                self.logger.debug(f"Node has protection label: {protection_key}={protection_value}")
                return True, None  # No timeout for protection labels

        # Check taints for deletion markers
        taints = node.spec.taints or []
        for taint in taints:
            if taint.key in self.deletion_taints and taint.effect == "NoSchedule":
                self.logger.debug(f"Found deletion taint: {taint.key}")

                # Use taint timestamp if available
                if taint.time_added:
                    taint_age = datetime.now(timezone.utc) - taint.time_added
                    return True, taint_age
                else:
                    # No timestamp available, assume it's been there for a while
                    return True, self.deletion_timeout + timedelta(minutes=1)

        return False, None

    def _has_unschedulable_taint(self, node: client.V1Node) -> bool:
        """Check if node has the unschedulable taint (cordoned)."""
        taints = node.spec.taints or []
        for taint in taints:
            if taint.key == "node.kubernetes.io/unschedulable" and taint.effect == "NoSchedule":
                return True
        return False

    def _is_node_unreachable(self, node: client.V1Node) -> bool:
        """Check if node is in unreachable state."""
        conditions = node.status.conditions or []
        for condition in conditions:
            if condition.type == "Ready" and condition.status == "Unknown":
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
