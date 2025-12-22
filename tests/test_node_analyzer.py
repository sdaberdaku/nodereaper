"""Tests for node analyzer module."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from kubernetes import client

from src.nodereaper.node_analyzer import NodeAnalyzer


class TestNodeAnalyzer(unittest.TestCase):
    """Test cases for NodeAnalyzer class."""

    def setUp(self):
        """Set up test environment."""
        self.analyzer = NodeAnalyzer(
            min_age=timedelta(minutes=10),
            deletion_timeout=timedelta(minutes=15),
            deletion_taints=[
                "karpenter.sh/disrupted",
                "cluster-autoscaler.kubernetes.io/scale-down",
                "node.kubernetes.io/unschedulable",
            ],
            protection_annotations={
                "karpenter.sh/do-not-evict": "true",
                "nodereaper.io/do-not-delete": "true",
            },
            protection_labels={
                "karpenter.sh/do-not-evict": "true",
                "nodereaper.io/do-not-delete": "true",
            },
        )

    def _create_mock_node(
        self,
        name: str,
        age_minutes: int = 15,
        annotations: dict = None,
        labels: dict = None,
        taints: list = None,
        ready_status: str = "True",
    ) -> client.V1Node:
        """Create a mock node for testing."""
        creation_time = datetime.now(timezone.utc) - timedelta(minutes=age_minutes)

        node = MagicMock(spec=client.V1Node)
        node.metadata.name = name
        node.metadata.creation_timestamp = creation_time
        node.metadata.annotations = annotations or {}
        node.metadata.labels = labels or {}
        node.spec.taints = taints or []

        # Mock node conditions
        ready_condition = MagicMock()
        ready_condition.type = "Ready"
        ready_condition.status = ready_status
        node.status.conditions = [ready_condition]

        return node

    def _create_mock_pod(self, name: str, owner_kind: str = "Deployment") -> client.V1Pod:
        """Create a mock pod for testing."""
        pod = MagicMock(spec=client.V1Pod)
        pod.metadata.name = name

        if owner_kind:
            owner_ref = MagicMock()
            owner_ref.kind = owner_kind
            pod.metadata.owner_references = [owner_ref]
        else:
            pod.metadata.owner_references = []

        return pod

    def test_node_too_young(self):
        """Test that young nodes are not deleted."""
        young_node = self._create_mock_node("young-node", age_minutes=5)

        should_delete, reason = self.analyzer.should_delete_node(young_node, [])

        self.assertFalse(should_delete)
        self.assertEqual(reason, "")

    def test_node_old_enough(self):
        """Test that old empty nodes are deleted."""
        old_node = self._create_mock_node("old-node", age_minutes=15)

        should_delete, reason = self.analyzer.should_delete_node(old_node, [])

        self.assertTrue(should_delete)
        self.assertEqual(reason, "empty")

    def test_protected_node(self):
        """Test that nodes with protection annotations are not deleted."""
        # Test with protection annotation
        protected_node = self._create_mock_node(
            "protected-node", annotations={"karpenter.sh/do-not-evict": "true"}
        )

        should_delete, reason = self.analyzer.should_delete_node(protected_node, [])

        self.assertFalse(should_delete)
        self.assertEqual(reason, "")

        # Test with custom protection annotation
        custom_protected_node = self._create_mock_node(
            "custom-protected-node", annotations={"nodereaper.io/do-not-delete": "true"}
        )

        should_delete, reason = self.analyzer.should_delete_node(custom_protected_node, [])

        self.assertFalse(should_delete)
        self.assertEqual(reason, "")

    def test_protected_node_labels(self):
        """Test that nodes with protection labels are not deleted."""
        # Test with protection label
        protected_node = self._create_mock_node(
            "protected-node", labels={"karpenter.sh/do-not-evict": "true"}
        )

        should_delete, reason = self.analyzer.should_delete_node(protected_node, [])

        self.assertFalse(should_delete)
        self.assertEqual(reason, "")

        # Test with custom protection label
        custom_protected_node = self._create_mock_node(
            "custom-protected-node", labels={"nodereaper.io/do-not-delete": "true"}
        )

        should_delete, reason = self.analyzer.should_delete_node(custom_protected_node, [])

        self.assertFalse(should_delete)
        self.assertEqual(reason, "")

        # Test with wrong label value (should not be protected)
        wrong_value_node = self._create_mock_node(
            "wrong-value-node", labels={"karpenter.sh/do-not-evict": "false"}
        )

        should_delete, reason = self.analyzer.should_delete_node(wrong_value_node, [])

        self.assertTrue(should_delete)  # Should be deleted because it's empty
        self.assertEqual(reason, "empty")

    def test_deletion_marked_node_with_timeout(self):
        """Test that nodes marked for deletion are protected for timeout period."""
        # Test with deletion taint - should be protected initially
        taint = MagicMock()
        taint.key = "karpenter.sh/disrupted"
        taint.effect = "NoSchedule"
        taint.time_added = datetime.now(timezone.utc) - timedelta(minutes=5)  # 5 minutes ago

        marked_node = self._create_mock_node("marked-node", taints=[taint])

        should_delete, reason = self.analyzer.should_delete_node(marked_node, [])

        # Should be protected because it's within the 15-minute timeout
        self.assertFalse(should_delete)
        self.assertEqual(reason, "")

        # Test with old deletion taint - should be taken over
        old_taint = MagicMock()
        old_taint.key = "karpenter.sh/disrupted"
        old_taint.effect = "NoSchedule"
        old_taint.time_added = datetime.now(timezone.utc) - timedelta(minutes=20)  # 20 minutes ago

        old_marked_node = self._create_mock_node("old-marked-node", taints=[old_taint])

        should_delete, reason = self.analyzer.should_delete_node(old_marked_node, [])

        # Should be deleted because timeout has expired and node is empty
        self.assertTrue(should_delete)
        self.assertEqual(reason, "takeover-empty")

    def test_unreachable_node(self):
        """Test that unreachable nodes are deleted."""
        unreachable_node = self._create_mock_node("unreachable-node", ready_status="Unknown")

        should_delete, reason = self.analyzer.should_delete_node(unreachable_node, [])

        self.assertTrue(should_delete)
        self.assertEqual(reason, "unreachable")

    def test_unschedulable_node(self):
        """Test that unschedulable (cordoned) nodes are deleted."""
        # Create unschedulable taint
        unschedulable_taint = MagicMock()
        unschedulable_taint.key = "node.kubernetes.io/unschedulable"
        unschedulable_taint.effect = "NoSchedule"
        unschedulable_taint.time_added = None  # No timestamp for unschedulable taint

        unschedulable_node = self._create_mock_node(
            "unschedulable-node", taints=[unschedulable_taint]
        )

        should_delete, reason = self.analyzer.should_delete_node(unschedulable_node, [])

        self.assertTrue(should_delete)
        self.assertEqual(reason, "unschedulable")

    def test_unschedulable_node_with_workloads(self):
        """Test that unschedulable nodes are deleted even with workloads."""
        # Create unschedulable taint
        unschedulable_taint = MagicMock()
        unschedulable_taint.key = "node.kubernetes.io/unschedulable"
        unschedulable_taint.effect = "NoSchedule"
        unschedulable_taint.time_added = None  # No timestamp for unschedulable taint

        unschedulable_node = self._create_mock_node(
            "unschedulable-node", taints=[unschedulable_taint]
        )
        deployment_pod = self._create_mock_pod("deployment-pod", "Deployment")

        should_delete, reason = self.analyzer.should_delete_node(
            unschedulable_node, [deployment_pod]
        )

        self.assertTrue(should_delete)
        self.assertEqual(reason, "unschedulable")

    def test_unschedulable_wrong_effect(self):
        """Test that nodes with unschedulable key but wrong effect are not deleted."""
        # Create taint with wrong effect
        wrong_effect_taint = MagicMock()
        wrong_effect_taint.key = "node.kubernetes.io/unschedulable"
        wrong_effect_taint.effect = "NoExecute"  # Wrong effect

        node = self._create_mock_node("node-wrong-effect", taints=[wrong_effect_taint])

        should_delete, reason = self.analyzer.should_delete_node(node, [])

        self.assertTrue(should_delete)  # Should still be deleted because it's empty
        self.assertEqual(reason, "empty")  # Not unschedulable, but empty

    def test_empty_node(self):
        """Test that empty nodes (only DaemonSet pods) are deleted."""
        empty_node = self._create_mock_node("empty-node")
        daemonset_pod = self._create_mock_pod("daemonset-pod", "DaemonSet")

        should_delete, reason = self.analyzer.should_delete_node(empty_node, [daemonset_pod])

        self.assertTrue(should_delete)
        self.assertEqual(reason, "empty")

    def test_node_with_workloads(self):
        """Test that nodes with non-DaemonSet pods are not deleted."""
        node_with_workloads = self._create_mock_node("workload-node")
        deployment_pod = self._create_mock_pod("deployment-pod", "Deployment")
        daemonset_pod = self._create_mock_pod("daemonset-pod", "DaemonSet")

        should_delete, reason = self.analyzer.should_delete_node(
            node_with_workloads, [deployment_pod, daemonset_pod]
        )

        self.assertFalse(should_delete)
        self.assertEqual(reason, "")

    def test_is_daemonset_pod(self):
        """Test DaemonSet pod detection."""
        daemonset_pod = self._create_mock_pod("ds-pod", "DaemonSet")
        deployment_pod = self._create_mock_pod("deploy-pod", "Deployment")

        self.assertTrue(self.analyzer._is_daemonset_pod(daemonset_pod))
        self.assertFalse(self.analyzer._is_daemonset_pod(deployment_pod))

    def test_has_unschedulable_taint(self):
        """Test unschedulable taint detection."""
        # Test with correct unschedulable taint
        unschedulable_taint = MagicMock()
        unschedulable_taint.key = "node.kubernetes.io/unschedulable"
        unschedulable_taint.effect = "NoSchedule"

        unschedulable_node = self._create_mock_node("unschedulable", taints=[unschedulable_taint])
        self.assertTrue(self.analyzer._has_unschedulable_taint(unschedulable_node))

        # Test with wrong effect
        wrong_effect_taint = MagicMock()
        wrong_effect_taint.key = "node.kubernetes.io/unschedulable"
        wrong_effect_taint.effect = "NoExecute"

        wrong_effect_node = self._create_mock_node("wrong-effect", taints=[wrong_effect_taint])
        self.assertFalse(self.analyzer._has_unschedulable_taint(wrong_effect_node))

        # Test with wrong key
        wrong_key_taint = MagicMock()
        wrong_key_taint.key = "example.com/custom-taint"
        wrong_key_taint.effect = "NoSchedule"

        wrong_key_node = self._create_mock_node("wrong-key", taints=[wrong_key_taint])
        self.assertFalse(self.analyzer._has_unschedulable_taint(wrong_key_node))

        # Test with no taints
        no_taints_node = self._create_mock_node("no-taints", taints=[])
        self.assertFalse(self.analyzer._has_unschedulable_taint(no_taints_node))

        # Test with None taints
        none_taints_node = self._create_mock_node("none-taints", taints=None)
        self.assertFalse(self.analyzer._has_unschedulable_taint(none_taints_node))

    def test_format_age(self):
        """Test age formatting."""
        test_cases = [
            (timedelta(seconds=30), "30s"),
            (timedelta(minutes=5), "5m"),
            (timedelta(hours=2), "2h"),
            (timedelta(days=1), "1d"),
            (timedelta(minutes=5, seconds=30), "5m"),  # Should round down
        ]

        for age, expected in test_cases:
            result = self.analyzer._format_age(age)
            self.assertEqual(result, expected, f"Failed for age: {age}")

    def test_get_node_info(self):
        """Test node info extraction."""
        node = self._create_mock_node("test-node")
        node.metadata.labels = {
            "node.kubernetes.io/instance-type": "m5.large",
            "topology.kubernetes.io/zone": "us-west-2a",
        }

        info = self.analyzer.get_node_info(node)

        self.assertEqual(info["name"], "test-node")
        self.assertEqual(info["instance_type"], "m5.large")
        self.assertEqual(info["zone"], "us-west-2a")
        self.assertIn("age", info)
        self.assertIn("creation_time", info)


if __name__ == "__main__":
    unittest.main()
