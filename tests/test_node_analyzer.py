"""
Unit tests for node analysis, deletion criteria, and finalizer cleanup logic.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from kubernetes import client as k8s

from nodereaper.k8s.node import NodeAnalyzer


class TestNodeAnalyzer:
    """Test NodeAnalyzer functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.analyzer = NodeAnalyzer(
            cluster_name="test-cluster",
            node_min_age=timedelta(minutes=30),
            deletion_timeout=timedelta(minutes=15),
            unhealthy_taints=["node.kubernetes.io/not-ready", "node.kubernetes.io/unreachable"],
            protection_annotations={"karpenter.sh/do-not-evict": "true"},
            protection_labels={"dedicated": "karpenter"},
            removable_finalizers=["karpenter.sh/termination", "test.finalizer"],
        )

    def create_mock_node(
        self,
        name="test-node",
        creation_timestamp=None,
        deletion_timestamp=None,
        labels=None,
        annotations=None,
        finalizers=None,
        taints=None,
        conditions=None,
    ):
        """Create a mock Kubernetes node."""
        node = Mock(spec=k8s.V1Node)

        # Metadata
        node.metadata = Mock()
        node.metadata.name = name
        node.metadata.creation_timestamp = creation_timestamp or datetime.now(timezone.utc)
        node.metadata.deletion_timestamp = deletion_timestamp
        node.metadata.labels = labels or {}
        node.metadata.annotations = annotations or {}
        node.metadata.finalizers = finalizers or []

        # Spec
        node.spec = Mock()
        node.spec.taints = taints or []

        # Status
        node.status = Mock()
        node.status.conditions = conditions or []

        return node

    def create_mock_pod(self, name="test-pod", owner_kind="Deployment"):
        """Create a mock Kubernetes pod."""
        pod = Mock(spec=k8s.V1Pod)
        pod.metadata = Mock()
        pod.metadata.name = name

        if owner_kind:
            owner_ref = Mock()
            owner_ref.kind = owner_kind
            pod.metadata.owner_references = [owner_ref]
        else:
            pod.metadata.owner_references = []

        return pod

    def create_mock_taint(self, key, effect="NoSchedule"):
        """Create a mock Kubernetes taint."""
        taint = Mock()
        taint.key = key
        taint.effect = effect
        return taint

    def create_mock_condition(self, condition_type, status):
        """Create a mock Kubernetes node condition."""
        condition = Mock()
        condition.type = condition_type
        condition.status = status
        return condition


class TestNodeAnalyzerInitialization(TestNodeAnalyzer):
    """Test NodeAnalyzer initialization."""

    def test_initialization_with_defaults(self):
        """Test NodeAnalyzer initialization with default values."""
        analyzer = NodeAnalyzer()

        # Should use values from settings module
        assert analyzer.cluster_name is not None
        assert analyzer.node_min_age is not None
        assert analyzer.deletion_timeout is not None
        assert isinstance(analyzer.unhealthy_taints, list)
        assert isinstance(analyzer.protection_annotations, dict)
        assert isinstance(analyzer.protection_labels, dict)
        assert isinstance(analyzer.removable_finalizers, list)

    def test_initialization_with_custom_values(self):
        """Test NodeAnalyzer initialization with custom values."""
        assert self.analyzer.cluster_name == "test-cluster"
        assert self.analyzer.node_min_age == timedelta(minutes=30)
        assert self.analyzer.deletion_timeout == timedelta(minutes=15)
        assert self.analyzer.unhealthy_taints == [
            "node.kubernetes.io/not-ready",
            "node.kubernetes.io/unreachable",
        ]
        assert self.analyzer.protection_annotations == {"karpenter.sh/do-not-evict": "true"}
        assert self.analyzer.protection_labels == {"dedicated": "karpenter"}
        assert self.analyzer.removable_finalizers == ["karpenter.sh/termination", "test.finalizer"]


class TestNodeInfo(TestNodeAnalyzer):
    """Test node information extraction."""

    def test_get_node_info_basic(self):
        """Test getting basic node information."""
        creation_time = datetime.now(timezone.utc) - timedelta(hours=1)
        node = self.create_mock_node(
            name="test-node",
            creation_timestamp=creation_time,
            labels={
                "node.kubernetes.io/instance-type": "m5.large",
                "topology.kubernetes.io/zone": "us-west-2a",
            },
        )

        info = self.analyzer.get_node_info(node)

        assert info["name"] == "test-node"
        assert info["cluster"] == "test-cluster"
        assert info["instance_type"] == "m5.large"
        assert info["zone"] == "us-west-2a"
        assert info["age"] == "1h"
        assert info["creation_time"] == creation_time.isoformat()

    def test_get_node_info_missing_labels(self):
        """Test getting node info with missing labels."""
        node = self.create_mock_node(name="test-node")

        info = self.analyzer.get_node_info(node)

        assert info["instance_type"] == "unknown"
        assert info["zone"] == "unknown"

    def test_format_age_seconds(self):
        """Test age formatting for seconds."""
        age = timedelta(seconds=45)
        formatted = self.analyzer._format_age(age)
        assert formatted == "45s"

    def test_format_age_minutes(self):
        """Test age formatting for minutes."""
        age = timedelta(minutes=30)
        formatted = self.analyzer._format_age(age)
        assert formatted == "30m"

    def test_format_age_hours(self):
        """Test age formatting for hours."""
        age = timedelta(hours=5)
        formatted = self.analyzer._format_age(age)
        assert formatted == "5h"

    def test_format_age_days(self):
        """Test age formatting for days."""
        age = timedelta(days=3)
        formatted = self.analyzer._format_age(age)
        assert formatted == "3d"


class TestNodeTerminatingState(TestNodeAnalyzer):
    """Test node terminating state detection."""

    def test_is_terminating_true(self):
        """Test node is terminating when deletion timestamp is set."""
        node = self.create_mock_node(deletion_timestamp=datetime.now(timezone.utc))

        assert self.analyzer.is_terminating(node) is True

    def test_is_terminating_false(self):
        """Test node is not terminating when deletion timestamp is None."""
        node = self.create_mock_node(deletion_timestamp=None)

        assert self.analyzer.is_terminating(node) is False


class TestNodeDeletionDecision(TestNodeAnalyzer):
    """Test node deletion decision logic."""

    def test_should_delete_node_protected_by_annotation(self):
        """Test node protected by annotation should not be deleted."""
        node = self.create_mock_node(annotations={"karpenter.sh/do-not-evict": "true"})
        pods = []

        should_delete, reason = self.analyzer.should_delete_node(node, pods)

        assert should_delete is False
        assert reason == "Node has protection annotation(s)"

    def test_should_delete_node_protected_by_label(self):
        """Test node protected by label should not be deleted."""
        node = self.create_mock_node(labels={"dedicated": "karpenter"})
        pods = []

        should_delete, reason = self.analyzer.should_delete_node(node, pods)

        assert should_delete is False
        assert reason == "Node has protection label(s)"

    def test_should_delete_node_too_young(self):
        """Test node too young should not be deleted."""
        # Node created 10 minutes ago (less than 30 minute minimum)
        creation_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        node = self.create_mock_node(creation_timestamp=creation_time)
        pods = []

        should_delete, reason = self.analyzer.should_delete_node(node, pods)

        assert should_delete is False
        assert reason == "Node is too young"

    def test_should_delete_node_unreachable(self):
        """Test unreachable node should be deleted."""
        creation_time = datetime.now(timezone.utc) - timedelta(hours=1)
        conditions = [self.create_mock_condition("Ready", "Unknown")]
        node = self.create_mock_node(creation_timestamp=creation_time, conditions=conditions)
        pods = []

        should_delete, reason = self.analyzer.should_delete_node(node, pods)

        assert should_delete is True
        assert reason == "Node is unreachable"

    def test_should_delete_node_not_ready(self):
        """Test not ready node should be deleted."""
        creation_time = datetime.now(timezone.utc) - timedelta(hours=1)
        conditions = [self.create_mock_condition("Ready", "False")]
        node = self.create_mock_node(creation_timestamp=creation_time, conditions=conditions)
        pods = []

        should_delete, reason = self.analyzer.should_delete_node(node, pods)

        assert should_delete is True
        assert reason == "Node is not ready"

    def test_should_delete_node_unhealthy_taint(self):
        """Test node with unhealthy taint should be deleted."""
        creation_time = datetime.now(timezone.utc) - timedelta(hours=1)
        taints = [self.create_mock_taint("node.kubernetes.io/not-ready", "NoExecute")]
        node = self.create_mock_node(creation_timestamp=creation_time, taints=taints)
        pods = []

        should_delete, reason = self.analyzer.should_delete_node(node, pods)

        assert should_delete is True
        assert reason == "Node has unhealthy taint(s)"

    def test_should_delete_node_empty(self):
        """Test empty node (only DaemonSet pods) should be deleted."""
        creation_time = datetime.now(timezone.utc) - timedelta(hours=1)
        node = self.create_mock_node(creation_timestamp=creation_time)
        pods = [
            self.create_mock_pod("daemonset-pod-1", "DaemonSet"),
            self.create_mock_pod("daemonset-pod-2", "DaemonSet"),
        ]

        should_delete, reason = self.analyzer.should_delete_node(node, pods)

        assert should_delete is True
        assert reason == "Node is empty"

    def test_should_delete_node_has_workload_pods(self):
        """Test node with workload pods should not be deleted."""
        creation_time = datetime.now(timezone.utc) - timedelta(hours=1)
        node = self.create_mock_node(creation_timestamp=creation_time)
        pods = [
            self.create_mock_pod("daemonset-pod", "DaemonSet"),
            self.create_mock_pod("deployment-pod", "Deployment"),
        ]

        should_delete, reason = self.analyzer.should_delete_node(node, pods)

        assert should_delete is False
        assert reason == "Node does not meet deletion criteria"


class TestFinalizerCleanup(TestNodeAnalyzer):
    """Test finalizer cleanup logic."""

    def test_should_cleanup_finalizers_not_terminating(self):
        """Test finalizer cleanup should not happen for non-terminating nodes."""
        node = self.create_mock_node(finalizers=["karpenter.sh/termination"])

        should_cleanup, reason = self.analyzer.should_cleanup_finalizers(node)

        assert should_cleanup is False
        assert reason == "Node is not in terminating state"

    def test_should_cleanup_finalizers_no_removable_finalizers_configured(self):
        """Test finalizer cleanup when no removable finalizers are configured."""
        analyzer = NodeAnalyzer(removable_finalizers=[])
        node = self.create_mock_node(
            deletion_timestamp=datetime.now(timezone.utc), finalizers=["some.finalizer"]
        )

        should_cleanup, reason = analyzer.should_cleanup_finalizers(node)

        assert should_cleanup is False
        assert reason == "No removable finalizers configured"

    def test_should_cleanup_finalizers_no_removable_finalizers_on_node(self):
        """Test finalizer cleanup when node has no removable finalizers."""
        deletion_time = datetime.now(timezone.utc) - timedelta(minutes=20)
        node = self.create_mock_node(
            deletion_timestamp=deletion_time, finalizers=["other.finalizer"]
        )

        should_cleanup, reason = self.analyzer.should_cleanup_finalizers(node)

        assert should_cleanup is False
        assert reason == "Node has no removable finalizers"

    def test_should_cleanup_finalizers_timeout_not_expired(self):
        """Test finalizer cleanup when timeout has not expired."""
        # Node terminating for 10 minutes (less than 15 minute timeout)
        deletion_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        node = self.create_mock_node(
            deletion_timestamp=deletion_time, finalizers=["karpenter.sh/termination"]
        )

        should_cleanup, reason = self.analyzer.should_cleanup_finalizers(node)

        assert should_cleanup is False
        assert reason == "Node deletion timeout has not expired"

    def test_should_cleanup_finalizers_success(self):
        """Test successful finalizer cleanup decision."""
        # Node terminating for 20 minutes (more than 15 minute timeout)
        deletion_time = datetime.now(timezone.utc) - timedelta(minutes=20)
        node = self.create_mock_node(
            deletion_timestamp=deletion_time, finalizers=["karpenter.sh/termination"]
        )

        should_cleanup, reason = self.analyzer.should_cleanup_finalizers(node)

        assert should_cleanup is True
        assert "Node in terminating state for 20m" in reason

    def test_finalizers_to_remove(self):
        """Test getting list of finalizers to remove."""
        node = self.create_mock_node(
            finalizers=["karpenter.sh/termination", "other.finalizer", "test.finalizer"]
        )

        to_remove = self.analyzer.finalizers_to_remove(node)

        assert set(to_remove) == {"karpenter.sh/termination", "test.finalizer"}

    def test_finalizers_to_keep(self):
        """Test getting list of finalizers to keep."""
        node = self.create_mock_node(
            finalizers=["karpenter.sh/termination", "other.finalizer", "test.finalizer"]
        )

        to_keep = self.analyzer.finalizers_to_keep(node)

        assert to_keep == ["other.finalizer"]

    def test_finalizers_empty_list(self):
        """Test finalizer operations with empty finalizer list."""
        node = self.create_mock_node(finalizers=[])

        to_remove = self.analyzer.finalizers_to_remove(node)
        to_keep = self.analyzer.finalizers_to_keep(node)

        assert to_remove == []
        assert to_keep == []


class TestNodeHealthChecks(TestNodeAnalyzer):
    """Test node health check methods."""

    def test_is_daemonset_pod_true(self):
        """Test identifying DaemonSet pod."""
        pod = self.create_mock_pod("test-pod", "DaemonSet")

        assert self.analyzer._is_daemonset_pod(pod) is True

    def test_is_daemonset_pod_false(self):
        """Test identifying non-DaemonSet pod."""
        pod = self.create_mock_pod("test-pod", "Deployment")

        assert self.analyzer._is_daemonset_pod(pod) is False

    def test_is_daemonset_pod_no_owner(self):
        """Test pod with no owner references."""
        pod = self.create_mock_pod("test-pod", None)

        assert self.analyzer._is_daemonset_pod(pod) is False

    def test_is_empty_all_daemonset_pods(self):
        """Test node is empty when all pods are DaemonSet pods."""
        pods = [
            self.create_mock_pod("pod1", "DaemonSet"),
            self.create_mock_pod("pod2", "DaemonSet"),
        ]

        assert self.analyzer._is_empty(pods) is True

    def test_is_empty_mixed_pods(self):
        """Test node is not empty when it has non-DaemonSet pods."""
        pods = [
            self.create_mock_pod("pod1", "DaemonSet"),
            self.create_mock_pod("pod2", "Deployment"),
        ]

        assert self.analyzer._is_empty(pods) is False

    def test_is_empty_no_pods(self):
        """Test node is empty when it has no pods."""
        pods = []

        assert self.analyzer._is_empty(pods) is True

    def test_has_unhealthy_taint_true(self):
        """Test node has unhealthy taint."""
        taints = [
            self.create_mock_taint("node.kubernetes.io/not-ready", "NoExecute"),
            self.create_mock_taint("other.taint", "NoSchedule"),
        ]
        node = self.create_mock_node(taints=taints)

        assert self.analyzer._has_unhealthy_taint(node) is True

    def test_has_unhealthy_taint_false(self):
        """Test node does not have unhealthy taint."""
        taints = [self.create_mock_taint("other.taint", "NoSchedule")]
        node = self.create_mock_node(taints=taints)

        assert self.analyzer._has_unhealthy_taint(node) is False

    def test_has_unhealthy_taint_wrong_effect(self):
        """Test unhealthy taint with wrong effect is ignored."""
        taints = [self.create_mock_taint("node.kubernetes.io/not-ready", "PreferNoSchedule")]
        node = self.create_mock_node(taints=taints)

        assert self.analyzer._has_unhealthy_taint(node) is False
