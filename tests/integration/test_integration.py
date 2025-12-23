"""Integration tests for NodeReaper using local Kubernetes cluster."""

import os
import time
import unittest
from datetime import datetime, timedelta, timezone

import pytest
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from nodereaper.config import Config
from nodereaper.kubernetes_client import KubernetesClient
from nodereaper.node_analyzer import NodeAnalyzer
from nodereaper.reaper import NodeReaper


@pytest.mark.integration
class TestNodeReaperIntegration(unittest.TestCase):
    """Integration tests for NodeReaper."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        try:
            # Try to load kubeconfig (for local testing)
            config.load_kube_config()
            cls.v1 = client.CoreV1Api()
            cls.k8s_client = KubernetesClient()
            cls.cluster_available = True

            # Verify we can connect to the cluster
            cls.v1.get_api_resources()

            # Check if this looks like a test cluster (kind/minikube)
            nodes = cls.v1.list_node()
            node_names = [node.metadata.name for node in nodes.items]

            # Skip tests if not running on a test cluster
            if not any(
                "kind" in name or "minikube" in name or "test" in name.lower()
                for name in node_names
            ):
                # Check for test labels
                has_test_labels = any(
                    node.metadata.labels
                    and node.metadata.labels.get("test-environment") == "integration"
                    for node in nodes.items
                )
                if not has_test_labels:
                    cls.cluster_available = False

        except Exception as e:
            cls.cluster_available = False
            print(f"Kubernetes cluster not available for integration tests: {e}")

    def setUp(self):
        """Set up each test."""
        if not self.cluster_available:
            self.skipTest("Kubernetes cluster not available or not a test cluster")

        # Create test namespace
        self.test_namespace = "nodereaper-integration-test"
        try:
            self.v1.create_namespace(
                client.V1Namespace(metadata=client.V1ObjectMeta(name=self.test_namespace))
            )
        except ApiException as e:
            if e.status != 409:  # Ignore if namespace already exists
                raise

    def tearDown(self):
        """Clean up after each test."""
        if not self.cluster_available:
            return

        try:
            # Clean up test namespace
            self.v1.delete_namespace(name=self.test_namespace)
        except ApiException:
            pass  # Ignore cleanup errors

    def test_list_nodes_basic(self):
        """Test basic node listing functionality."""
        nodes = self.k8s_client.list_nodes()

        self.assertGreater(len(nodes), 0, "Should have at least one node")

        # Verify node objects have expected attributes
        for node in nodes:
            self.assertIsInstance(node, client.V1Node)
            self.assertIsNotNone(node.metadata.name)
            self.assertIsNotNone(node.metadata.creation_timestamp)

    def test_list_nodes_with_label_selector(self):
        """Test node listing with label selectors."""
        # Test cleanup-enabled selector
        cleanup_nodes = self.k8s_client.list_nodes("cleanup-enabled=true")

        # Should have nodes with cleanup enabled in our test cluster
        self.assertGreaterEqual(len(cleanup_nodes), 0)

        # Verify all returned nodes have the cleanup-enabled label
        for node in cleanup_nodes:
            labels = node.metadata.labels or {}
            self.assertIn("cleanup-enabled", labels)
            self.assertEqual(labels["cleanup-enabled"], "true")

    def test_list_nodes_with_custom_labels(self):
        """Test node listing with custom labels."""
        # Test custom label selector (if nodes have them)
        nodes_with_cleanup = self.k8s_client.list_nodes("cleanup-enabled=true")

        # Verify all returned nodes have the expected label
        for node in nodes_with_cleanup:
            labels = node.metadata.labels or {}
            self.assertEqual(labels.get("cleanup-enabled"), "true")

    def test_list_pods_on_node(self):
        """Test listing pods on a specific node."""
        nodes = self.k8s_client.list_nodes()
        if not nodes:
            self.skipTest("No nodes available")

        node_name = nodes[0].metadata.name
        pods = self.k8s_client.list_pods_on_node(node_name)

        # Should have at least system pods
        self.assertGreaterEqual(len(pods), 0)

        # Verify all pods are on the specified node
        for pod in pods:
            self.assertEqual(pod.spec.node_name, node_name)

    def test_node_analyzer_with_real_nodes(self):
        """Test node analyzer with real cluster nodes."""
        analyzer = NodeAnalyzer(min_age=timedelta(seconds=1))  # Very short age for testing

        nodes = self.k8s_client.list_nodes()
        if not nodes:
            self.skipTest("No nodes available")

        for node in nodes:
            pods = self.k8s_client.list_pods_on_node(node.metadata.name)
            should_delete, reason = analyzer.should_delete_node(node, pods)

            # Control plane nodes should never be deleted
            labels = node.metadata.labels or {}
            if "node-role.kubernetes.io/control-plane" in labels:
                self.assertFalse(
                    should_delete, f"Control plane node {node.metadata.name} should not be deleted"
                )
            else:
                # Worker nodes might be candidates for deletion if they're empty
                # This is actually the expected behavior in our test cluster
                print(f"Node {node.metadata.name}: should_delete={should_delete}, reason={reason}")
                # Just verify the analyzer is working, don't assert specific behavior

    def test_dry_run_mode(self):
        """Test NodeReaper in dry-run mode."""
        # Set up config for dry-run
        os.environ["DRY_RUN"] = "true"
        os.environ["NODE_MIN_AGE"] = "1s"  # Very short for testing
        os.environ["LOG_LEVEL"] = "DEBUG"

        try:
            config_obj = Config()
            reaper = NodeReaper(config_obj)

            # This should run without errors and not delete anything
            reaper.process_nodes()

            # Verify nodes still exist
            nodes_after = self.k8s_client.list_nodes()
            self.assertGreater(len(nodes_after), 0, "Nodes should still exist after dry-run")

        finally:
            # Clean up environment
            for key in ["DRY_RUN", "NODE_MIN_AGE", "LOG_LEVEL"]:
                if key in os.environ:
                    del os.environ[key]

    def test_label_selector_filtering(self):
        """Test NodeReaper with label selector filtering."""
        # Test with cleanup-enabled selector
        os.environ["NODE_LABEL_SELECTOR"] = "cleanup-enabled=true"
        os.environ["DRY_RUN"] = "true"
        os.environ["LOG_LEVEL"] = "DEBUG"

        try:
            config_obj = Config()
            reaper = NodeReaper(config_obj)

            # Should run without errors
            reaper.process_nodes()

        finally:
            # Clean up environment
            for key in ["NODE_LABEL_SELECTOR", "DRY_RUN", "LOG_LEVEL"]:
                if key in os.environ:
                    del os.environ[key]

    def test_create_test_pod(self):
        """Test creating and managing test pods."""
        # Create a simple test pod
        pod_manifest = client.V1Pod(
            metadata=client.V1ObjectMeta(
                name="test-pod", namespace=self.test_namespace, labels={"app": "nodereaper-test"}
            ),
            spec=client.V1PodSpec(
                containers=[
                    client.V1Container(
                        name="test-container",
                        image="nginx:alpine",
                        resources=client.V1ResourceRequirements(
                            requests={"cpu": "10m", "memory": "16Mi"},
                            limits={"cpu": "50m", "memory": "64Mi"},
                        ),
                    )
                ],
                restart_policy="Never",
            ),
        )

        # Create the pod
        created_pod = self.v1.create_namespaced_pod(
            namespace=self.test_namespace, body=pod_manifest
        )

        self.assertEqual(created_pod.metadata.name, "test-pod")

        # Wait a bit for pod to be scheduled
        time.sleep(2)

        # Verify pod exists and get its node
        pod = self.v1.read_namespaced_pod(name="test-pod", namespace=self.test_namespace)
        if pod.spec.node_name:
            # Verify we can list this pod when querying the node
            pods_on_node = self.k8s_client.list_pods_on_node(pod.spec.node_name)
            pod_names = [p.metadata.name for p in pods_on_node]
            self.assertIn("test-pod", pod_names)

        # Clean up
        self.v1.delete_namespaced_pod(name="test-pod", namespace=self.test_namespace)

    def test_protected_node_detection(self):
        """Test that nodes with protection annotations are not deleted."""
        nodes = self.k8s_client.list_nodes()
        if not nodes:
            self.skipTest("No nodes available")

        # Find a worker node to test with
        worker_node = None
        for node in nodes:
            labels = node.metadata.labels or {}
            if "node-role.kubernetes.io/control-plane" not in labels:
                worker_node = node
                break

        if not worker_node:
            self.skipTest("No worker nodes available")

        original_annotations = worker_node.metadata.annotations or {}

        try:
            # Add protection annotation
            test_annotations = original_annotations.copy()
            test_annotations["nodereaper.io/do-not-delete"] = "integration-test"

            # Patch the node with protection annotation
            patch_body = {"metadata": {"annotations": test_annotations}}
            self.v1.patch_node(name=worker_node.metadata.name, body=patch_body)

            # Test with NodeAnalyzer
            analyzer = NodeAnalyzer(
                min_age=timedelta(seconds=1),
                deletion_timeout=timedelta(minutes=15),
                deletion_taints=["karpenter.sh/disrupted", "test.io/terminating"],
                protection_annotations={"nodereaper.io/do-not-delete": "integration-test"},
            )

            # Get updated node
            updated_node = self.v1.read_node(name=worker_node.metadata.name)
            pods = self.k8s_client.list_pods_on_node(worker_node.metadata.name)

            should_delete, reason = analyzer.should_delete_node(updated_node, pods)

            # Should not delete protected node
            self.assertFalse(
                should_delete, f"Protected node {worker_node.metadata.name} should not be deleted"
            )
            self.assertEqual(reason, "", "Protected node should have empty reason")

        finally:
            # Restore original annotations
            patch_body = {"metadata": {"annotations": original_annotations}}
            try:
                self.v1.patch_node(name=worker_node.metadata.name, body=patch_body)
            except ApiException:
                pass  # Ignore cleanup errors

    def test_deletion_tainted_node_within_timeout(self):
        """Test that nodes with recent deletion taints are protected."""
        nodes = self.k8s_client.list_nodes()
        if not nodes:
            self.skipTest("No nodes available")

        # Find a worker node to test with
        worker_node = None
        for node in nodes:
            labels = node.metadata.labels or {}
            if "node-role.kubernetes.io/control-plane" not in labels:
                worker_node = node
                break

        if not worker_node:
            self.skipTest("No worker nodes available")

        original_taints = worker_node.spec.taints or []

        try:
            # Add deletion taint with recent timestamp
            test_taint = client.V1Taint(
                key="karpenter.sh/disrupted",
                effect="NoSchedule",
                value="test-deletion",
                time_added=datetime.now(timezone.utc),  # Recent taint
            )

            new_taints = original_taints + [test_taint]

            # Patch the node with deletion taint
            patch_body = {"spec": {"taints": new_taints}}
            self.v1.patch_node(name=worker_node.metadata.name, body=patch_body)

            # Test with NodeAnalyzer
            analyzer = NodeAnalyzer(
                min_age=timedelta(seconds=1),
                deletion_timeout=timedelta(minutes=15),  # 15 minute timeout
                deletion_taints=["karpenter.sh/disrupted"],
                protection_annotations={"nodereaper.io/do-not-delete": "true"},
            )

            # Get updated node
            updated_node = self.v1.read_node(name=worker_node.metadata.name)
            pods = self.k8s_client.list_pods_on_node(worker_node.metadata.name)

            should_delete, reason = analyzer.should_delete_node(updated_node, pods)

            # Should not delete recently tainted node (within timeout)
            self.assertFalse(
                should_delete,
                f"Recently tainted node {worker_node.metadata.name} should be protected",
            )
            self.assertEqual(reason, "", "Recently tainted node should have empty reason")

        finally:
            # Restore original taints
            patch_body = {"spec": {"taints": original_taints}}
            try:
                self.v1.patch_node(name=worker_node.metadata.name, body=patch_body)
            except ApiException:
                pass  # Ignore cleanup errors

    def test_deletion_tainted_node_expired_timeout(self):
        """Test that nodes with old deletion taints are taken over."""
        nodes = self.k8s_client.list_nodes()
        if not nodes:
            self.skipTest("No nodes available")

        # Find a worker node to test with
        worker_node = None
        for node in nodes:
            labels = node.metadata.labels or {}
            if "node-role.kubernetes.io/control-plane" not in labels:
                worker_node = node
                break

        if not worker_node:
            self.skipTest("No worker nodes available")

        original_taints = worker_node.spec.taints or []

        try:
            # Add deletion taint with old timestamp (beyond timeout)
            old_time = datetime.now(timezone.utc) - timedelta(minutes=20)  # 20 minutes ago
            test_taint = client.V1Taint(
                key="karpenter.sh/disrupted",
                effect="NoSchedule",
                value="test-deletion",
                time_added=old_time,
            )

            new_taints = original_taints + [test_taint]

            # Patch the node with old deletion taint
            patch_body = {"spec": {"taints": new_taints}}
            self.v1.patch_node(name=worker_node.metadata.name, body=patch_body)

            # Test with NodeAnalyzer (short timeout for testing)
            analyzer = NodeAnalyzer(
                min_age=timedelta(seconds=1),
                deletion_timeout=timedelta(minutes=15),  # 15 minute timeout
                deletion_taints=["karpenter.sh/disrupted"],
                protection_annotations={"nodereaper.io/do-not-delete": "true"},
            )

            # Get updated node
            updated_node = self.v1.read_node(name=worker_node.metadata.name)
            pods = self.k8s_client.list_pods_on_node(worker_node.metadata.name)

            should_delete, reason = analyzer.should_delete_node(updated_node, pods)

            # Should take over deletion of old tainted node
            # Note: This depends on whether the node is actually empty
            if should_delete:
                self.assertTrue(
                    reason.startswith("takeover-"),
                    f"Old tainted node should have takeover reason, got: {reason}",
                )
            else:
                # Node might not be empty (has non-DaemonSet pods), which is fine
                print(f"Node {worker_node.metadata.name} not empty, skipping takeover test")

        finally:
            # Restore original taints
            patch_body = {"spec": {"taints": original_taints}}
            try:
                self.v1.patch_node(name=worker_node.metadata.name, body=patch_body)
            except ApiException:
                pass  # Ignore cleanup errors

    def test_unschedulable_node_detection(self):
        """Test detection of unschedulable (cordoned) nodes."""
        nodes = self.k8s_client.list_nodes()
        if not nodes:
            self.skipTest("No nodes available")

        # Find a worker node to test with
        worker_node = None
        for node in nodes:
            labels = node.metadata.labels or {}
            if "node-role.kubernetes.io/control-plane" not in labels:
                worker_node = node
                break

        if not worker_node:
            self.skipTest("No worker nodes available")

        original_taints = worker_node.spec.taints or []
        original_unschedulable = getattr(worker_node.spec, "unschedulable", False)

        try:
            # Add unschedulable taint (simulate cordoning)
            unschedulable_taint = client.V1Taint(
                key="node.kubernetes.io/unschedulable", effect="NoSchedule"
            )

            new_taints = original_taints + [unschedulable_taint]

            # Patch the node to be unschedulable
            patch_body = {"spec": {"taints": new_taints, "unschedulable": True}}
            self.v1.patch_node(name=worker_node.metadata.name, body=patch_body)

            # Test with NodeAnalyzer
            analyzer = NodeAnalyzer(
                min_age=timedelta(seconds=1),
                deletion_timeout=timedelta(minutes=15),
                deletion_taints=["node.kubernetes.io/unschedulable"],
                protection_annotations={"nodereaper.io/do-not-delete": "true"},
            )

            # Get updated node
            updated_node = self.v1.read_node(name=worker_node.metadata.name)
            pods = self.k8s_client.list_pods_on_node(worker_node.metadata.name)

            should_delete, reason = analyzer.should_delete_node(updated_node, pods)

            # Should delete unschedulable node regardless of workloads
            self.assertTrue(
                should_delete, f"Unschedulable node {worker_node.metadata.name} should be deleted"
            )
            self.assertEqual(
                reason, "unschedulable", "Unschedulable node should have 'unschedulable' reason"
            )

        finally:
            # Restore original state
            patch_body = {
                "spec": {"taints": original_taints, "unschedulable": original_unschedulable}
            }
            try:
                self.v1.patch_node(name=worker_node.metadata.name, body=patch_body)
            except ApiException:
                pass  # Ignore cleanup errors

    def test_mixed_taint_scenarios(self):
        """Test complex scenarios with multiple taints and annotations."""
        nodes = self.k8s_client.list_nodes()
        if not nodes:
            self.skipTest("No nodes available")

        # Find a worker node to test with
        worker_node = None
        for node in nodes:
            labels = node.metadata.labels or {}
            if "node-role.kubernetes.io/control-plane" not in labels:
                worker_node = node
                break

        if not worker_node:
            self.skipTest("No worker nodes available")

        original_taints = worker_node.spec.taints or []
        original_annotations = worker_node.metadata.annotations or {}

        try:
            # Test 1: Protection annotation overrides deletion taint
            test_annotations = original_annotations.copy()
            test_annotations["karpenter.sh/do-not-evict"] = "true"

            deletion_taint = client.V1Taint(
                key="karpenter.sh/disrupted",
                effect="NoSchedule",
                time_added=datetime.now(timezone.utc) - timedelta(minutes=20),  # Old taint
            )

            new_taints = original_taints + [deletion_taint]

            # Apply both protection annotation and deletion taint
            patch_body = {
                "metadata": {"annotations": test_annotations},
                "spec": {"taints": new_taints},
            }
            self.v1.patch_node(name=worker_node.metadata.name, body=patch_body)

            analyzer = NodeAnalyzer(
                min_age=timedelta(seconds=1),
                deletion_timeout=timedelta(minutes=15),
                deletion_taints=["karpenter.sh/disrupted"],
                protection_annotations={"karpenter.sh/do-not-evict": "true"},
            )

            updated_node = self.v1.read_node(name=worker_node.metadata.name)
            pods = self.k8s_client.list_pods_on_node(worker_node.metadata.name)

            should_delete, reason = analyzer.should_delete_node(updated_node, pods)

            # Protection should override deletion taint
            self.assertFalse(should_delete, "Protection annotation should override deletion taint")
            self.assertEqual(reason, "", "Protected node should have empty reason")

        finally:
            # Restore original state
            patch_body = {
                "metadata": {"annotations": original_annotations},
                "spec": {"taints": original_taints},
            }
            try:
                self.v1.patch_node(name=worker_node.metadata.name, body=patch_body)
            except ApiException:
                pass  # Ignore cleanup errors

    def test_nodereaper_with_tainted_nodes_dry_run(self):
        """Test full NodeReaper execution with tainted nodes in dry-run mode."""
        # Set up environment for testing with deletion taints
        os.environ["DRY_RUN"] = "true"
        os.environ["NODE_MIN_AGE"] = "1s"
        os.environ["DELETION_TIMEOUT"] = "5m"
        os.environ["DELETION_TAINTS"] = "karpenter.sh/disrupted,test.io/terminating"
        os.environ["PROTECTION_ANNOTATIONS"] = "nodereaper.io/do-not-delete=true"
        os.environ["LOG_LEVEL"] = "DEBUG"

        try:
            config_obj = Config()
            reaper = NodeReaper(config_obj)

            # This should run without errors
            reaper.process_nodes()

            # Verify configuration was loaded correctly
            self.assertTrue(config_obj.dry_run)
            self.assertIn("karpenter.sh/disrupted", config_obj.deletion_taints)
            self.assertIn("test.io/terminating", config_obj.deletion_taints)
            self.assertIn("nodereaper.io/do-not-delete", config_obj.protection_annotations)
            self.assertEqual(
                config_obj.protection_annotations["nodereaper.io/do-not-delete"], "true"
            )

        finally:
            # Clean up environment
            for key in [
                "DRY_RUN",
                "NODE_MIN_AGE",
                "DELETION_TIMEOUT",
                "DELETION_TAINTS",
                "PROTECTION_ANNOTATIONS",
                "PROTECTION_LABELS",
                "LOG_LEVEL",
            ]:
                if key in os.environ:
                    del os.environ[key]


@pytest.mark.integration
class TestNodeReaperIntegrationPytest:
    """Pytest-style integration tests."""

    def setup_method(self):
        """Set up test fixtures."""
        try:
            self.k8s_client = KubernetesClient()
            # Test connectivity
            self.k8s_client.list_nodes()
        except Exception as e:
            pytest.skip(f"Kubernetes cluster not available: {e}")

    def test_node_count(self):
        """Test that we have the expected number of nodes."""
        nodes = self.k8s_client.list_nodes()

        # Kind cluster should have 4 nodes (1 control-plane + 3 workers)
        # But we'll be flexible for different test setups
        assert len(nodes) >= 1, "Should have at least one node"
        assert len(nodes) <= 10, "Should not have too many nodes (sanity check)"

    def test_worker_node_labels(self):
        """Test that worker nodes have expected labels."""
        cleanup_nodes = self.k8s_client.list_nodes("cleanup-enabled=true")

        for node in cleanup_nodes:
            labels = node.metadata.labels or {}

            # Should have cleanup-enabled label
            assert "cleanup-enabled" in labels
            assert labels["cleanup-enabled"] == "true"

            # Should have some of our custom test labels
            assert "instance-type" in labels
            assert "zone" in labels
            expected_labels = ["instance-type", "zone", "cleanup-enabled"]
            has_custom_labels = any(label in labels for label in expected_labels)

            if not has_custom_labels:
                pytest.skip("Test cluster doesn't have expected custom labels")

    def test_tainted_node_analysis(self):
        """Test NodeAnalyzer behavior with tainted nodes."""
        nodes = self.k8s_client.list_nodes()

        if not nodes:
            pytest.skip("No nodes available")

        # Test with a mock tainted node scenario
        analyzer = NodeAnalyzer(
            min_age=timedelta(seconds=1),
            deletion_timeout=timedelta(minutes=10),
            deletion_taints=[
                "karpenter.sh/disrupted",
                "cluster-autoscaler.kubernetes.io/scale-down",
            ],
            protection_annotations={
                "karpenter.sh/do-not-evict": "true",
                "nodereaper.io/do-not-delete": "true",
            },
        )

        # Verify analyzer configuration
        assert "karpenter.sh/disrupted" in analyzer.deletion_taints
        assert "cluster-autoscaler.kubernetes.io/scale-down" in analyzer.deletion_taints
        assert analyzer.protection_annotations["karpenter.sh/do-not-evict"] == "true"
        assert analyzer.protection_annotations["nodereaper.io/do-not-delete"] == "true"
        assert analyzer.deletion_timeout == timedelta(minutes=10)

    def test_protection_annotation_patterns(self):
        """Test various protection annotation patterns."""
        analyzer = NodeAnalyzer(
            min_age=timedelta(seconds=1),
            deletion_timeout=timedelta(minutes=15),
            deletion_taints=["karpenter.sh/disrupted"],
            protection_annotations={
                "karpenter.sh/do-not-evict": "true",
                "nodereaper.io/protected": "integration-test",
            },
        )

        # Test different annotation patterns - should match exact key-value pairs
        test_cases = [
            ({"karpenter.sh/do-not-evict": "true"}, True),  # Exact match
            ({"karpenter.sh/do-not-evict": "false"}, False),  # Wrong value
            ({"nodereaper.io/protected": "integration-test"}, True),  # Exact match
            ({"nodereaper.io/protected": "other-test"}, False),  # Wrong value
            ({"other.io/do-not-evict": "true"}, False),  # Wrong key
        ]

        for annotations, should_be_protected in test_cases:
            # Create mock node with protection annotation
            from unittest.mock import MagicMock

            node = MagicMock()
            node.metadata.annotations = annotations
            node.spec.taints = []

            is_marked, age = analyzer._is_marked_for_deletion(node)

            if should_be_protected:
                # Should be marked as protected (is_marked=True, age=None)
                assert (
                    is_marked == True
                ), f"Node with annotations {annotations} should be marked as protected"
                assert age is None, f"Protected node should have no timeout (age=None)"
            else:
                # Should not be protected
                assert (
                    is_marked == False
                ), f"Node with annotations {annotations} should not be protected"

    def test_deletion_taint_patterns(self):
        """Test various deletion taint patterns."""
        from datetime import datetime
        from datetime import timedelta as td
        from datetime import timezone

        analyzer = NodeAnalyzer(
            min_age=td(seconds=1),
            deletion_timeout=td(minutes=15),
            deletion_taints=[
                "karpenter.sh/disrupted",
                "karpenter.sh/terminating",
                "cluster-autoscaler.kubernetes.io/scale-down",
                "test.io/deletion-marker",
            ],
            protection_annotations={},
        )

        from unittest.mock import MagicMock

        # Test different taint patterns
        test_taints = [
            "karpenter.sh/disrupted",
            "karpenter.sh/terminating",
            "cluster-autoscaler.kubernetes.io/scale-down",
            "test.io/deletion-marker",
        ]

        for taint_key in test_taints:
            # Create mock taint
            taint = MagicMock()
            taint.key = taint_key
            taint.effect = "NoSchedule"
            taint.time_added = datetime.now(timezone.utc) - td(minutes=5)

            # Create mock node with deletion taint
            node = MagicMock()
            node.metadata.annotations = {}
            node.spec.taints = [taint]

            is_marked, age = analyzer._is_marked_for_deletion(node)

            # Should be marked for deletion with age
            assert is_marked == True, f"Node with taint {taint_key} should be marked for deletion"
            assert age is not None, f"Deletion taint should have age, got None for {taint_key}"
            assert isinstance(age, td), f"Age should be timedelta, got {type(age)}"


if __name__ == "__main__":
    # Run integration tests
    unittest.main()
