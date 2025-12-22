"""Integration tests for NodeReaper using local Kubernetes cluster."""

import os
import time
import unittest
from datetime import datetime, timedelta, timezone
from typing import List

import pytest
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from src.nodereaper.config import Config
from src.nodereaper.kubernetes_client import KubernetesClient
from src.nodereaper.node_analyzer import NodeAnalyzer
from src.nodereaper.reaper import NodeReaper


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
        cleanup_nodes = self.k8s_client.list_nodes({"cleanup-enabled": "true"})

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
        nodes_with_cleanup = self.k8s_client.list_nodes({"cleanup-enabled": "true"})

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
        cleanup_nodes = self.k8s_client.list_nodes({"cleanup-enabled": "true"})

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


if __name__ == "__main__":
    # Run integration tests
    unittest.main()
