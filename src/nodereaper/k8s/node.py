"""
Node analysis engine for determining deletion eligibility and finalizer cleanup.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

import logging
from datetime import datetime, timedelta, timezone

from kubernetes import client as k8s

from nodereaper.settings import (
    CLUSTER_NAME,
    DELETION_TIMEOUT,
    NODE_MIN_AGE,
    PROTECTION_ANNOTATIONS,
    PROTECTION_LABELS,
    REMOVABLE_FINALIZERS,
    UNHEALTHY_TAINTS,
)

logger = logging.getLogger(__name__)


class NodeAnalyzer:
    """Analyzes nodes to determine if they should be deleted."""

    def __init__(
        self,
        cluster_name: str = None,
        node_min_age: timedelta = None,
        deletion_timeout: timedelta = None,
        unhealthy_taints: list[str] = None,
        protection_annotations: dict[str, str] = None,
        protection_labels: dict[str, str] = None,
        removable_finalizers: list[str] = None,
    ) -> None:
        """Initialize node analyzer.

        :param cluster_name: Name of the cluster for notifications
        :param node_min_age: Minimum age before nodes can be deleted
        :param deletion_timeout: Timeout before finalizer cleanup
        :param unhealthy_taints: List of taint keys indicating unhealthy nodes
        :param protection_annotations: Annotations that protect nodes from deletion
        :param protection_labels: Labels that protect nodes from deletion
        :param removable_finalizers: Finalizers safe to remove during cleanup
        """
        self.cluster_name = CLUSTER_NAME if cluster_name is None else cluster_name
        self.node_min_age = NODE_MIN_AGE if node_min_age is None else node_min_age
        self.deletion_timeout = DELETION_TIMEOUT if deletion_timeout is None else deletion_timeout
        self.unhealthy_taints = UNHEALTHY_TAINTS if unhealthy_taints is None else unhealthy_taints
        self.protection_annotations = (
            PROTECTION_ANNOTATIONS if protection_annotations is None else protection_annotations
        )
        self.protection_labels = (
            PROTECTION_LABELS if protection_labels is None else protection_labels
        )
        self.removable_finalizers = (
            REMOVABLE_FINALIZERS if removable_finalizers is None else removable_finalizers
        )

        logger.info(
            f"Node analyzer initialized with "
            f"cluster_name={self.cluster_name}, "
            f"node_min_age={self.node_min_age}, "
            f"deletion_timeout={self.deletion_timeout}, "
            f"unhealthy_taints={self.unhealthy_taints}, "
            f"protection_annotations={self.protection_annotations}, "
            f"protection_labels={self.protection_labels}, "
            f"removable_finalizers={self.removable_finalizers}"
        )

    def get_node_info(self, node: k8s.V1Node) -> dict[str, str]:
        """Get node information for logging and notifications.

        :param node: Kubernetes node object
        :return: Dictionary with node information
        """
        labels = node.metadata.labels or {}
        age = self._get_age(node)

        return {
            "name": node.metadata.name,
            "age": self._format_age(age),
            "cluster": self.cluster_name,
            "instance_type": labels.get("node.kubernetes.io/instance-type", "unknown"),
            "zone": labels.get("topology.kubernetes.io/zone", "unknown"),
            "creation_time": node.metadata.creation_timestamp.isoformat(),
        }

    @staticmethod
    def is_terminating(node: k8s.V1Node) -> bool:
        """Check if node is in terminating state.

        :param node: Kubernetes node object
        :return: True if node has deletion timestamp
        """
        return node.metadata.deletion_timestamp is not None

    def should_delete_node(self, node: k8s.V1Node, pods: list[k8s.V1Pod]) -> tuple[bool, str]:
        """Determine if a node should be deleted.

        :param node: Kubernetes node object
        :param pods: List of pods running on the node
        :return: Tuple of (should_delete: bool, reason: str)
        """
        if self._has_protection_annotation(node):
            return False, "Node has protection annotation(s)"
        if self._has_protection_label(node):
            return False, "Node has protection label(s)"
        if not self._is_old_enough(node):
            return False, "Node is too young"
        if self._is_unreachable(node):
            return True, "Node is unreachable"
        if self._is_not_ready(node):
            return True, "Node is not ready"
        if self._has_unhealthy_taint(node):
            return True, "Node has unhealthy taint(s)"
        if self._is_empty(pods):
            return True, "Node is empty"
        return False, "Node does not meet deletion criteria"

    def should_cleanup_finalizers(self, node: k8s.V1Node) -> tuple[bool, str]:
        """Determine if node finalizers should be cleaned up.

        :param node: Kubernetes node object
        :return: Tuple of (should_cleanup: bool, reason: str)
        """
        if not self.removable_finalizers:
            return False, "No removable finalizers configured"
        if not self.is_terminating(node):
            return False, "Node is not in terminating state"
        if not self._has_removable_finalizers(node):
            return False, "Node has no removable finalizers"
        if not self._has_expired_deletion_timeout(node):
            return False, "Node deletion timeout has not expired"
        return (
            True,
            f"Node in terminating state for {self._format_age(self._get_terminating_age(node))}",
        )

    def _has_removable_finalizers(self, node: k8s.V1Node) -> bool:
        """Check if node has any removable finalizers.

        :param node: Kubernetes node object
        :return: True if node has removable finalizers
        """
        node_finalizers = node.metadata.finalizers or []
        return any(f in self.removable_finalizers for f in node_finalizers)

    def finalizers_to_remove(self, node: k8s.V1Node) -> list[str]:
        """Get list of finalizers to remove from node.

        :param node: Kubernetes node object
        :return: List of finalizer names to remove
        """
        node_finalizers = node.metadata.finalizers or []
        return [f for f in node_finalizers if f in self.removable_finalizers]

    def finalizers_to_keep(self, node: k8s.V1Node) -> list[str]:
        """Get list of finalizers to keep on node.

        :param node: Kubernetes node object
        :return: List of finalizer names to keep
        """
        node_finalizers = node.metadata.finalizers or []
        return [f for f in node_finalizers if f not in self.removable_finalizers]

    def _has_protection_annotation(self, node: k8s.V1Node) -> bool:
        return self._has_matching_metadata(node.metadata.annotations, self.protection_annotations)

    def _has_protection_label(self, node: k8s.V1Node) -> bool:
        return self._has_matching_metadata(node.metadata.labels, self.protection_labels)

    @staticmethod
    def _has_matching_metadata(
        metadata: dict[str, str] | None, protection_rules: dict[str, str]
    ) -> bool:
        values = metadata or {}
        return any(values.get(key) == expected for key, expected in protection_rules.items())

    def _has_expired_deletion_timeout(self, node: k8s.V1Node) -> bool:
        return self._get_terminating_age(node) >= self.deletion_timeout

    def _is_old_enough(self, node: k8s.V1Node) -> bool:
        """Check if node is old enough to be deleted.

        :param node: Kubernetes node object
        :return: True if node age exceeds minimum age threshold
        """
        return self._get_age(node) >= self.node_min_age

    @staticmethod
    def _get_age(node: k8s.V1Node) -> timedelta:
        """Get the age of a node.

        :param node: Kubernetes node object
        :return: Time since node creation
        """
        creation_time: datetime = node.metadata.creation_timestamp
        return datetime.now(timezone.utc) - creation_time

    @staticmethod
    def _get_terminating_age(node: k8s.V1Node) -> timedelta:
        """Get the age since the node entered terminating state.

        :param node: Kubernetes node object
        :return: Time since deletion timestamp was set
        """
        deletion_time: datetime = node.metadata.deletion_timestamp
        if deletion_time:
            return datetime.now(timezone.utc) - deletion_time
        return timedelta()

    @staticmethod
    def _format_age(age: timedelta) -> str:
        """Format timedelta into human readable string.

        :param age: Time duration
        :return: Formatted string (e.g., "5m", "2h", "3d")
        """
        total_seconds = int(age.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            return f"{total_seconds // 60}m"
        elif total_seconds < 86400:
            return f"{total_seconds // 3600}h"
        else:
            return f"{total_seconds // 86400}d"

    @staticmethod
    def _is_unreachable(node: k8s.V1Node) -> bool:
        """Check if node is in unreachable state.

        :param node: Kubernetes node object
        :return: True if node Ready condition is Unknown
        """
        conditions = node.status.conditions or []
        return any(
            condition.type == "Ready" and condition.status == "Unknown" for condition in conditions
        )

    @staticmethod
    def _is_not_ready(node: k8s.V1Node) -> bool:
        """Check if node is not ready.

        :param node: Kubernetes node object
        :return: True if node Ready condition is False
        """
        conditions = node.status.conditions or []
        return any(
            condition.type == "Ready" and condition.status == "False" for condition in conditions
        )

    def _has_unhealthy_taint(self, node: k8s.V1Node) -> bool:
        """Check if node has unhealthy taints.

        :param node: Kubernetes node object
        :return: True if node has configured unhealthy taints
        """
        taints = node.spec.taints or []
        return any(
            taint.key in self.unhealthy_taints and taint.effect in {"NoExecute", "NoSchedule"}
            for taint in taints
        )

    @staticmethod
    def _is_empty(pods: list[k8s.V1Pod]) -> bool:
        """Check if node only has DaemonSet pods running.

        :param pods: List of pods on the node
        :return: True if all pods are DaemonSet pods
        """
        return all(NodeAnalyzer._is_daemonset_pod(pod) for pod in pods)

    @staticmethod
    def _is_daemonset_pod(pod: k8s.V1Pod) -> bool:
        """Check if pod is owned by a DaemonSet.

        :param pod: Kubernetes pod object
        :return: True if pod is owned by a DaemonSet
        """
        owner_references = pod.metadata.owner_references or []
        return any(owner.kind == "DaemonSet" for owner in owner_references)
