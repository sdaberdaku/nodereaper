"""
Unit tests for Kubernetes API client, node operations, and finalizer management.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

from unittest.mock import Mock, patch

import pytest
from kubernetes import client as k8s
from kubernetes import config as k8s_config
from kubernetes.client import ApiException

from nodereaper.k8s.client import KubernetesClient
from nodereaper.k8s.exception import KubernetesException


class TestKubernetesClientInitialization:
    """Test KubernetesClient initialization."""

    @patch("nodereaper.k8s.client.k8s_config.load_incluster_config")
    @patch("nodereaper.k8s.client.k8s.CoreV1Api")
    def test_initialization_in_cluster(self, mock_core_v1_api, mock_load_incluster):
        """Test initialization with in-cluster config."""
        mock_api_instance = Mock()
        mock_core_v1_api.return_value = mock_api_instance

        client = KubernetesClient()

        mock_load_incluster.assert_called_once()
        mock_core_v1_api.assert_called_once()
        assert client.v1 is mock_api_instance

    @patch("nodereaper.k8s.client.k8s_config.load_incluster_config")
    @patch("nodereaper.k8s.client.k8s_config.load_kube_config")
    @patch("nodereaper.k8s.client.k8s_config.list_kube_config_contexts")
    @patch("nodereaper.k8s.client.k8s.CoreV1Api")
    @patch("nodereaper.k8s.client.TEST_KUBE_CONTEXT_NAME", "kind-test")
    def test_initialization_local_config(
        self, mock_core_v1_api, mock_list_contexts, mock_load_kube_config, mock_load_incluster
    ):
        """Test initialization with local kubeconfig."""
        # Simulate in-cluster config failure
        mock_load_incluster.side_effect = k8s_config.ConfigException("Not in cluster")

        # Mock successful local config
        mock_current_context = {"name": "kind-test"}
        mock_list_contexts.return_value = (None, mock_current_context)

        mock_api_instance = Mock()
        mock_core_v1_api.return_value = mock_api_instance

        client = KubernetesClient()

        mock_load_incluster.assert_called_once()
        mock_load_kube_config.assert_called_once()
        mock_list_contexts.assert_called_once()
        assert client.v1 is mock_api_instance

    @patch("nodereaper.k8s.client.k8s_config.load_incluster_config")
    @patch("nodereaper.k8s.client.k8s_config.load_kube_config")
    @patch("nodereaper.k8s.client.k8s_config.list_kube_config_contexts")
    @patch("nodereaper.k8s.client.TEST_KUBE_CONTEXT_NAME", "kind-test")
    def test_initialization_wrong_context(
        self, mock_list_contexts, mock_load_kube_config, mock_load_incluster
    ):
        """Test initialization fails with wrong context."""
        # Simulate in-cluster config failure
        mock_load_incluster.side_effect = k8s_config.ConfigException("Not in cluster")

        # Mock wrong context
        mock_current_context = {"name": "wrong-context"}
        mock_list_contexts.return_value = (None, mock_current_context)

        with pytest.raises(KubernetesException) as exc_info:
            KubernetesClient()

        assert "Unexpected kube-context 'wrong-context' name" in str(exc_info.value)

    @patch("nodereaper.k8s.client.k8s_config.load_incluster_config")
    @patch("nodereaper.k8s.client.k8s_config.load_kube_config")
    def test_initialization_config_failure(self, mock_load_kube_config, mock_load_incluster):
        """Test initialization fails when both configs fail."""
        mock_load_incluster.side_effect = k8s_config.ConfigException("Not in cluster")
        mock_load_kube_config.side_effect = k8s_config.ConfigException("No kubeconfig")

        with pytest.raises(KubernetesException) as exc_info:
            KubernetesClient()

        assert "Failed to load Kubernetes config" in str(exc_info.value)

    @patch("nodereaper.k8s.client.k8s_config.load_incluster_config")
    @patch("nodereaper.k8s.client.k8s_config.load_kube_config")
    def test_initialization_unexpected_error(self, mock_load_kube_config, mock_load_incluster):
        """Test initialization handles unexpected errors."""
        mock_load_incluster.side_effect = k8s_config.ConfigException("Not in cluster")
        mock_load_kube_config.side_effect = RuntimeError("Unexpected error")

        with pytest.raises(KubernetesException) as exc_info:
            KubernetesClient()

        assert "Unexpected error loading kube config" in str(exc_info.value)


class TestKubernetesClientMethods:
    """Test KubernetesClient methods."""

    def setup_method(self):
        """Set up test environment."""
        with patch("nodereaper.k8s.client.k8s_config.load_incluster_config"), patch(
            "nodereaper.k8s.client.k8s.CoreV1Api"
        ) as mock_core_v1_api:
            self.mock_v1_api = Mock()
            mock_core_v1_api.return_value = self.mock_v1_api
            self.client = KubernetesClient()

    def create_mock_node(self, name="test-node"):
        """Create a mock Kubernetes node."""
        node = Mock(spec=k8s.V1Node)
        node.metadata = Mock()
        node.metadata.name = name
        return node

    def create_mock_pod(self, name="test-pod"):
        """Create a mock Kubernetes pod."""
        pod = Mock(spec=k8s.V1Pod)
        pod.metadata = Mock()
        pod.metadata.name = name
        return pod

    def test_list_nodes_no_selector(self):
        """Test listing nodes without label selector."""
        mock_nodes = [self.create_mock_node("node1"), self.create_mock_node("node2")]
        mock_node_list = Mock()
        mock_node_list.items = mock_nodes
        self.mock_v1_api.list_node.return_value = mock_node_list

        result = self.client.list_nodes("")

        self.mock_v1_api.list_node.assert_called_once_with(label_selector=None)
        assert result == mock_nodes

    def test_list_nodes_with_selector(self):
        """Test listing nodes with label selector."""
        mock_nodes = [self.create_mock_node("node1")]
        mock_node_list = Mock()
        mock_node_list.items = mock_nodes
        self.mock_v1_api.list_node.return_value = mock_node_list

        result = self.client.list_nodes("cleanup=enabled")

        self.mock_v1_api.list_node.assert_called_once_with(label_selector="cleanup=enabled")
        assert result == mock_nodes

    def test_list_nodes_api_exception(self):
        """Test list_nodes handles API exceptions."""
        self.mock_v1_api.list_node.side_effect = ApiException(status=403, reason="Forbidden")

        with pytest.raises(KubernetesException):
            self.client.list_nodes("")

    def test_list_pods_on_node(self):
        """Test listing pods on a specific node."""
        mock_pods = [self.create_mock_pod("pod1"), self.create_mock_pod("pod2")]
        mock_pod_list = Mock()
        mock_pod_list.items = mock_pods
        self.mock_v1_api.list_pod_for_all_namespaces.return_value = mock_pod_list

        result = self.client.list_pods_on_node("test-node")

        self.mock_v1_api.list_pod_for_all_namespaces.assert_called_once_with(
            field_selector="spec.nodeName=test-node"
        )
        assert result == mock_pods

    def test_list_pods_on_node_api_exception(self):
        """Test list_pods_on_node handles API exceptions."""
        self.mock_v1_api.list_pod_for_all_namespaces.side_effect = ApiException(
            status=404, reason="Not Found"
        )

        with pytest.raises(KubernetesException):
            self.client.list_pods_on_node("test-node")

    def test_delete_node_success(self):
        """Test successful node deletion."""
        self.client.delete_node("test-node")

        self.mock_v1_api.delete_node.assert_called_once_with(
            name="test-node", grace_period_seconds=0
        )

    def test_delete_node_already_deleted(self):
        """Test deleting node that's already deleted (404)."""
        self.mock_v1_api.delete_node.side_effect = ApiException(status=404, reason="Not Found")

        # Should not raise exception
        self.client.delete_node("test-node")

        self.mock_v1_api.delete_node.assert_called_once()

    def test_delete_node_other_api_exception(self):
        """Test delete_node handles other API exceptions."""
        self.mock_v1_api.delete_node.side_effect = ApiException(status=403, reason="Forbidden")

        with pytest.raises(KubernetesException):
            self.client.delete_node("test-node")

    def test_cleanup_stuck_finalizers_success(self):
        """Test successful finalizer cleanup."""
        finalizers_to_remove = ["finalizer1", "finalizer2"]
        finalizers_to_keep = ["finalizer3"]

        self.client.cleanup_stuck_finalizers("test-node", finalizers_to_remove, finalizers_to_keep)

        expected_patch = {"metadata": {"finalizers": ["finalizer3"]}}
        self.mock_v1_api.patch_node.assert_called_once_with(name="test-node", body=expected_patch)

    def test_cleanup_stuck_finalizers_no_finalizers_to_remove(self):
        """Test finalizer cleanup with no finalizers to remove."""
        finalizers_to_remove = []
        finalizers_to_keep = ["finalizer1"]

        self.client.cleanup_stuck_finalizers("test-node", finalizers_to_remove, finalizers_to_keep)

        # Should not call patch_node
        self.mock_v1_api.patch_node.assert_not_called()

    def test_cleanup_stuck_finalizers_node_already_deleted(self):
        """Test finalizer cleanup when node is already deleted."""
        self.mock_v1_api.patch_node.side_effect = ApiException(status=404, reason="Not Found")

        # Should not raise exception
        self.client.cleanup_stuck_finalizers("test-node", ["finalizer1"], [])

        self.mock_v1_api.patch_node.assert_called_once()

    def test_cleanup_stuck_finalizers_api_exception(self):
        """Test finalizer cleanup handles API exceptions."""
        self.mock_v1_api.patch_node.side_effect = ApiException(status=403, reason="Forbidden")

        with pytest.raises(KubernetesException):
            self.client.cleanup_stuck_finalizers("test-node", ["finalizer1"], [])


class TestKubernetesClientIntegration:
    """Test KubernetesClient integration scenarios."""

    def setup_method(self):
        """Set up test environment."""
        with patch("nodereaper.k8s.client.k8s_config.load_incluster_config"), patch(
            "nodereaper.k8s.client.k8s.CoreV1Api"
        ) as mock_core_v1_api:
            self.mock_v1_api = Mock()
            mock_core_v1_api.return_value = self.mock_v1_api
            self.client = KubernetesClient()

    def test_full_node_cleanup_workflow(self):
        """Test complete node cleanup workflow."""
        # Setup mocks for list_nodes
        mock_node = Mock(spec=k8s.V1Node)
        mock_node.metadata.name = "test-node"
        mock_node_list = Mock()
        mock_node_list.items = [mock_node]
        self.mock_v1_api.list_node.return_value = mock_node_list

        # Setup mocks for list_pods_on_node
        mock_pod_list = Mock()
        mock_pod_list.items = []
        self.mock_v1_api.list_pod_for_all_namespaces.return_value = mock_pod_list

        # Execute workflow
        nodes = self.client.list_nodes("cleanup=enabled")
        pods = self.client.list_pods_on_node("test-node")
        self.client.delete_node("test-node")

        # Verify calls
        assert len(nodes) == 1
        assert nodes[0].metadata.name == "test-node"
        assert len(pods) == 0

        self.mock_v1_api.list_node.assert_called_once_with(label_selector="cleanup=enabled")
        self.mock_v1_api.list_pod_for_all_namespaces.assert_called_once_with(
            field_selector="spec.nodeName=test-node"
        )
        self.mock_v1_api.delete_node.assert_called_once_with(
            name="test-node", grace_period_seconds=0
        )

    def test_finalizer_cleanup_workflow(self):
        """Test finalizer cleanup workflow."""
        # Test cleanup with finalizers to remove
        self.client.cleanup_stuck_finalizers(
            "stuck-node", ["stuck.finalizer", "another.finalizer"], ["keep.finalizer"]
        )

        expected_patch = {"metadata": {"finalizers": ["keep.finalizer"]}}
        self.mock_v1_api.patch_node.assert_called_once_with(name="stuck-node", body=expected_patch)

    def test_error_handling_chain(self):
        """Test error handling propagation through decorator."""
        # Test that ApiException is properly converted to KubernetesException
        self.mock_v1_api.list_node.side_effect = ApiException(
            status=500, reason="Internal Server Error"
        )

        with pytest.raises(KubernetesException) as exc_info:
            self.client.list_nodes("")

        assert "Unexpected error when running list_nodes" in str(exc_info.value)
        assert "HTTP 500 - Internal Server Error" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, ApiException)
