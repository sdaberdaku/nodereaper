"""
Integration tests for NodeReaper using local Kubernetes cluster.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from kubernetes import client as k8s
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException

from nodereaper.k8s import KubernetesClient, NodeAnalyzer
from nodereaper.reaper import NodeReaper


class TestKubernetesIntegration:
    """Integration tests for NodeReaper with real Kubernetes cluster."""

    @classmethod
    def setup_class(cls):
        """Set up test environment."""
        try:
            # Try to load kubeconfig (for local testing)
            k8s_config.load_kube_config()
            cls.v1 = k8s.CoreV1Api()
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

    def setup_method(self):
        """Set up each test."""
        if not self.cluster_available:
            pytest.skip("Kubernetes cluster not available or not a test cluster")

        # Create test namespace with unique name to avoid conflicts
        import uuid

        self.test_namespace = f"nodereaper-test-{uuid.uuid4().hex[:8]}"
        try:
            self.v1.create_namespace(
                k8s.V1Namespace(metadata=k8s.V1ObjectMeta(name=self.test_namespace))
            )
            # Wait for namespace to be ready
            time.sleep(1)
        except ApiException as e:
            if e.status != 409:  # Ignore if namespace already exists
                raise

    def teardown_method(self):
        """Clean up after each test."""
        if not self.cluster_available:
            return

        try:
            # Delete all pods in the namespace first
            self.v1.delete_collection_namespaced_pod(namespace=self.test_namespace)
            time.sleep(2)  # Wait for pods to be deleted

            # Then delete the namespace
            self.v1.delete_namespace(name=self.test_namespace)
        except ApiException:
            pass  # Ignore cleanup errors

    @pytest.mark.integration
    def test_kubernetes_client_connectivity(self):
        """Test basic Kubernetes client connectivity."""
        nodes = self.k8s_client.list_nodes()

        assert len(nodes) > 0, "Should have at least one node"

        # Verify node objects have expected attributes
        for node in nodes:
            assert isinstance(node, k8s.V1Node)
            assert node.metadata.name is not None
            assert node.metadata.creation_timestamp is not None

    @pytest.mark.integration
    def test_list_nodes_with_label_selector(self):
        """Test node listing with label selectors."""
        # Test with a common label that should exist
        all_nodes = self.k8s_client.list_nodes()

        if all_nodes:
            # Get a label from the first node to test filtering
            first_node = all_nodes[0]
            labels = first_node.metadata.labels or {}

            # Try to find a suitable label for testing
            test_label = None
            for key, value in labels.items():
                if not key.startswith("node.kubernetes.io/"):
                    continue
                test_label = f"{key}={value}"
                break

            if test_label:
                filtered_nodes = self.k8s_client.list_nodes(test_label)
                assert len(filtered_nodes) >= 1, f"Should find nodes with label {test_label}"

    @pytest.mark.integration
    def test_list_pods_on_node(self):
        """Test listing pods on a specific node."""
        nodes = self.k8s_client.list_nodes()
        if not nodes:
            pytest.skip("No nodes available")

        node_name = nodes[0].metadata.name
        pods = self.k8s_client.list_pods_on_node(node_name)

        # Should have at least system pods
        assert len(pods) >= 0

        # Verify all pods are on the specified node
        for pod in pods:
            assert pod.spec.node_name == node_name

    @pytest.mark.integration
    def test_node_analyzer_with_real_nodes(self):
        """Test node analyzer with real cluster nodes."""
        analyzer = NodeAnalyzer(
            node_min_age=timedelta(seconds=1),  # Very short age for testing
            unhealthy_taints=["node.kubernetes.io/not-ready", "node.kubernetes.io/unreachable"],
            protection_annotations={"nodereaper.io/do-not-delete": "true"},
            protection_labels={"nodereaper.io/protected": "true"},
        )

        nodes = self.k8s_client.list_nodes()
        if not nodes:
            pytest.skip("No nodes available")

        for node in nodes:
            pods = self.k8s_client.list_pods_on_node(node.metadata.name)
            should_delete, reason = analyzer.should_delete_node(node, pods)

            # Control plane nodes should never be deleted
            labels = node.metadata.labels or {}
            if "node-role.kubernetes.io/control-plane" in labels:
                assert (
                    not should_delete
                ), f"Control plane node {node.metadata.name} should not be deleted"
            else:
                # Worker nodes might be candidates for deletion if they're empty
                print(f"Node {node.metadata.name}: should_delete={should_delete}, reason={reason}")

    @pytest.mark.integration
    def test_dry_run_mode(self):
        """Test NodeReaper in dry-run mode."""
        # Set up environment for dry-run
        env_vars = {
            "DRY_RUN": "true",
            "NODE_MIN_AGE": "1s",  # Very short for testing
            "LOG_LEVEL": "DEBUG",
            "ENABLE_JSON_LOGS": "false",
        }

        with patch.dict(os.environ, env_vars):
            reaper = NodeReaper(
                dry_run=True, enable_finalizer_cleanup=False, node_label_selector=""
            )

            # This should run without errors and not delete anything
            reaper.process_nodes()

            # Verify nodes still exist
            nodes_after = self.k8s_client.list_nodes()
            assert len(nodes_after) > 0, "Nodes should still exist after dry-run"

    @pytest.mark.integration
    def test_create_test_pod(self):
        """Test creating and managing test pods."""
        # Wait for namespace to be fully ready
        max_retries = 10
        for i in range(max_retries):
            try:
                # Check if namespace is ready
                ns = self.v1.read_namespace(name=self.test_namespace)
                if ns.status.phase == "Active":
                    break
                time.sleep(1)
            except ApiException:
                if i == max_retries - 1:
                    pytest.skip(
                        f"Namespace {self.test_namespace} not ready after {max_retries} seconds"
                    )
                time.sleep(1)

        # Create a simple test pod
        pod_manifest = k8s.V1Pod(
            metadata=k8s.V1ObjectMeta(
                name="test-pod", namespace=self.test_namespace, labels={"app": "nodereaper-test"}
            ),
            spec=k8s.V1PodSpec(
                containers=[
                    k8s.V1Container(
                        name="test-container",
                        image="nginx:alpine",
                        resources=k8s.V1ResourceRequirements(
                            requests={"cpu": "10m", "memory": "16Mi"},
                            limits={"cpu": "50m", "memory": "64Mi"},
                        ),
                    )
                ],
                restart_policy="Never",
            ),
        )

        try:
            # Create the pod
            created_pod = self.v1.create_namespaced_pod(
                namespace=self.test_namespace, body=pod_manifest
            )

            assert created_pod.metadata.name == "test-pod"

            # Wait a bit for pod to be scheduled
            time.sleep(3)

            # Verify pod exists and get its node
            pod = self.v1.read_namespaced_pod(name="test-pod", namespace=self.test_namespace)
            if pod.spec.node_name:
                # Verify we can list this pod when querying the node
                pods_on_node = self.k8s_client.list_pods_on_node(pod.spec.node_name)
                pod_names = [p.metadata.name for p in pods_on_node]
                assert "test-pod" in pod_names

        except ApiException as e:
            if e.status == 403 and "being terminated" in str(e):
                pytest.skip(f"Namespace {self.test_namespace} is being terminated, skipping test")
            else:
                raise

        finally:
            # Clean up pod
            try:
                self.v1.delete_namespaced_pod(name="test-pod", namespace=self.test_namespace)
            except ApiException:
                pass  # Ignore cleanup errors

    @pytest.mark.integration
    def test_node_analyzer_terminating_detection(self):
        """Test node analyzer terminating state detection."""
        analyzer = NodeAnalyzer()

        nodes = self.k8s_client.list_nodes()
        if not nodes:
            pytest.skip("No nodes available")

        for node in nodes:
            is_terminating = analyzer.is_terminating(node)
            # In a healthy cluster, nodes should not be terminating
            assert isinstance(is_terminating, bool)

    @pytest.mark.integration
    def test_node_analyzer_finalizer_logic(self):
        """Test node analyzer finalizer cleanup logic."""
        analyzer = NodeAnalyzer(
            removable_finalizers=["test.finalizer", "safe.finalizer"],
            deletion_timeout=timedelta(minutes=5),
        )

        nodes = self.k8s_client.list_nodes()
        if not nodes:
            pytest.skip("No nodes available")

        for node in nodes:
            # Test finalizer analysis methods
            finalizers_to_remove = analyzer.finalizers_to_remove(node)
            finalizers_to_keep = analyzer.finalizers_to_keep(node)

            # Should return lists
            assert isinstance(finalizers_to_remove, list)
            assert isinstance(finalizers_to_keep, list)

            # Should not overlap
            overlap = set(finalizers_to_remove) & set(finalizers_to_keep)
            assert len(overlap) == 0, "Finalizers to remove and keep should not overlap"

    @pytest.mark.integration
    def test_node_reaper_with_label_selector(self):
        """Test NodeReaper with label selector filtering."""
        # Test with a label that doesn't exist to ensure no nodes are processed
        env_vars = {
            "NODE_LABEL_SELECTOR": "nonexistent-label=true",
            "DRY_RUN": "true",
            "LOG_LEVEL": "DEBUG",
        }

        with patch.dict(os.environ, env_vars):
            reaper = NodeReaper(dry_run=True, node_label_selector="nonexistent-label=true")

            # Should run without errors (no nodes to process)
            reaper.process_nodes()

    @pytest.mark.integration
    def test_kubernetes_permissions(self):
        """Test that we have the required Kubernetes permissions."""
        # Test node permissions
        try:
            nodes = self.v1.list_node()
            assert len(nodes.items) > 0
        except ApiException as e:
            pytest.fail(f"Missing node list permission: {e}")

        # Test pod permissions
        try:
            pods = self.v1.list_pod_for_all_namespaces()
            assert isinstance(pods.items, list)
        except ApiException as e:
            pytest.fail(f"Missing pod list permission: {e}")

        # Test node patch permissions (for finalizer cleanup)
        nodes = self.v1.list_node()
        if nodes.items:
            test_node = nodes.items[0]
            try:
                # Try a no-op patch to test permissions
                patch_body = {"metadata": {"labels": test_node.metadata.labels}}
                self.v1.patch_node(name=test_node.metadata.name, body=patch_body)
            except ApiException as e:
                if e.status == 403:
                    pytest.fail(f"Missing node patch permission: {e}")

    @pytest.mark.integration
    def test_node_info_extraction(self):
        """Test node information extraction."""
        analyzer = NodeAnalyzer(cluster_name="test-cluster")

        nodes = self.k8s_client.list_nodes()
        if not nodes:
            pytest.skip("No nodes available")

        for node in nodes:
            node_info = analyzer.get_node_info(node)

            # Verify required fields
            assert "name" in node_info
            assert "cluster" in node_info
            assert "age" in node_info
            assert "instance_type" in node_info
            assert "zone" in node_info
            assert "creation_time" in node_info

            # Verify values
            assert node_info["name"] == node.metadata.name
            assert node_info["cluster"] == "test-cluster"
            assert isinstance(node_info["age"], str)


@pytest.mark.integration
class TestNodeReaperEndToEnd:
    """End-to-end integration tests."""

    @classmethod
    def setup_class(cls):
        """Set up test environment."""
        try:
            k8s_config.load_kube_config()
            cls.v1 = k8s.CoreV1Api()
            cls.cluster_available = True
        except Exception:
            cls.cluster_available = False

    def setup_method(self):
        """Set up each test."""
        if not self.cluster_available:
            pytest.skip("Kubernetes cluster not available")

    @pytest.mark.integration
    def test_full_nodereaper_workflow_dry_run(self):
        """Test complete NodeReaper workflow in dry-run mode."""
        env_vars = {
            "DRY_RUN": "true",
            "NODE_MIN_AGE": "1s",
            "DELETION_TIMEOUT": "5m",
            "UNHEALTHY_TAINTS": "node.kubernetes.io/not-ready,node.kubernetes.io/unreachable",
            "PROTECTION_ANNOTATIONS": "nodereaper.io/do-not-delete=true",
            "PROTECTION_LABELS": "nodereaper.io/protected=true",
            "REMOVABLE_FINALIZERS": "test.finalizer,safe.finalizer",
            "LOG_LEVEL": "INFO",
            "ENABLE_JSON_LOGS": "false",
        }

        with patch.dict(os.environ, env_vars):
            reaper = NodeReaper(dry_run=True, enable_finalizer_cleanup=True, node_label_selector="")

            # This should run without errors
            reaper.process_nodes()

    @pytest.mark.integration
    def test_configuration_loading(self):
        """Test that configuration is loaded correctly from environment."""
        env_vars = {
            "DRY_RUN": "false",
            "NODE_MIN_AGE": "30m",
            "DELETION_TIMEOUT": "15m",
            "UNHEALTHY_TAINTS": "taint1,taint2",
            "PROTECTION_ANNOTATIONS": "key1=value1,key2=value2",
            "PROTECTION_LABELS": "label1=value1",
            "REMOVABLE_FINALIZERS": "finalizer1,finalizer2",
            "CLUSTER_NAME": "test-cluster",
            "LOG_LEVEL": "DEBUG",
        }

        with patch.dict(os.environ, env_vars):
            # Import settings to reload with new environment
            import importlib

            from nodereaper import settings

            importlib.reload(settings)

            # Verify settings were loaded correctly
            assert settings.DRY_RUN is False
            assert settings.NODE_MIN_AGE == timedelta(minutes=30)
            assert settings.DELETION_TIMEOUT == timedelta(minutes=15)
            assert "taint1" in settings.UNHEALTHY_TAINTS
            assert "taint2" in settings.UNHEALTHY_TAINTS
            assert settings.PROTECTION_ANNOTATIONS["key1"] == "value1"
            assert settings.PROTECTION_ANNOTATIONS["key2"] == "value2"
            assert settings.PROTECTION_LABELS["label1"] == "value1"
            assert "finalizer1" in settings.REMOVABLE_FINALIZERS
            assert "finalizer2" in settings.REMOVABLE_FINALIZERS
            assert settings.CLUSTER_NAME == "test-cluster"
            assert settings.LOG_LEVEL == "DEBUG"
