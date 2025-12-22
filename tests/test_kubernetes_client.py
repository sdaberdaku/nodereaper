"""Tests for Kubernetes client module."""

import unittest
from unittest.mock import MagicMock, patch

from kubernetes.client.rest import ApiException

from src.nodereaper.kubernetes_client import KubernetesClient


class TestKubernetesClient(unittest.TestCase):
    """Test cases for KubernetesClient class."""

    def setUp(self):
        """Set up test environment."""
        with patch("kubernetes.config.load_incluster_config"):
            with patch("kubernetes.client.CoreV1Api"):
                self.client = KubernetesClient()
                self.client.v1 = MagicMock()

    def test_list_nodes_with_label_selector(self):
        """Test node listing with label selector."""
        mock_nodes = MagicMock()
        mock_nodes.items = ["node1", "node2"]
        self.client.v1.list_node.return_value = mock_nodes

        label_selector = {"cleanup-enabled": "true"}
        result = self.client.list_nodes(label_selector)

        self.assertEqual(result, ["node1", "node2"])
        self.client.v1.list_node.assert_called_once_with(label_selector="cleanup-enabled=true")

    def test_list_nodes_without_label_selector(self):
        """Test node listing without label selector."""
        mock_nodes = MagicMock()
        mock_nodes.items = ["node1", "node2"]
        self.client.v1.list_node.return_value = mock_nodes

        result = self.client.list_nodes()

        self.assertEqual(result, ["node1", "node2"])
        self.client.v1.list_node.assert_called_once_with(label_selector=None)

    def test_list_nodes_multiple_labels(self):
        """Test node listing with multiple labels."""
        mock_nodes = MagicMock()
        mock_nodes.items = ["node1"]
        self.client.v1.list_node.return_value = mock_nodes

        label_selector = {"instance-type": "m5.large", "zone": "us-west-2a"}
        result = self.client.list_nodes(label_selector)

        self.assertEqual(result, ["node1"])
        # Should be called with comma-separated labels (order may vary)
        call_args = self.client.v1.list_node.call_args[1]["label_selector"]
        self.assertIn("instance-type=m5.large", call_args)
        self.assertIn("zone=us-west-2a", call_args)
        self.assertIn(",", call_args)

    def test_list_nodes_failure(self):
        """Test failed node listing."""
        self.client.v1.list_node.side_effect = ApiException("API Error")

        with self.assertRaises(ApiException):
            self.client.list_nodes()

    def test_list_pods_on_node_success(self):
        """Test successful pod listing for a node."""
        mock_pods = MagicMock()
        mock_pods.items = ["pod1", "pod2"]
        self.client.v1.list_pod_for_all_namespaces.return_value = mock_pods

        result = self.client.list_pods_on_node("test-node")

        self.assertEqual(result, ["pod1", "pod2"])
        self.client.v1.list_pod_for_all_namespaces.assert_called_once_with(
            field_selector="spec.nodeName=test-node"
        )

    def test_list_pods_on_node_failure(self):
        """Test failed pod listing for a node."""
        self.client.v1.list_pod_for_all_namespaces.side_effect = ApiException("API Error")

        with self.assertRaises(ApiException):
            self.client.list_pods_on_node("test-node")

    def test_delete_node_success(self):
        """Test successful node deletion."""
        self.client.v1.delete_node.return_value = None

        result = self.client.delete_node("test-node")

        self.assertTrue(result)
        self.client.v1.delete_node.assert_called_once_with(name="test-node")

    def test_delete_node_failure(self):
        """Test failed node deletion."""
        self.client.v1.delete_node.side_effect = ApiException("API Error")

        result = self.client.delete_node("test-node")

        self.assertFalse(result)

    def test_connectivity_success(self):
        """Test successful connectivity test."""
        self.client.v1.get_api_resources.return_value = None

        result = self.client.test_connectivity()

        self.assertTrue(result)

    def test_connectivity_failure(self):
        """Test failed connectivity test."""
        self.client.v1.get_api_resources.side_effect = Exception("Connection Error")

        result = self.client.test_connectivity()

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
