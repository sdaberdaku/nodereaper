"""Tests for Kubernetes client module."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from kubernetes.client.rest import ApiException

from src.nodereaper.config import Config
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
        self.client.v1.delete_node.assert_called_once_with(name="test-node", grace_period_seconds=0)

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

    def test_finalizer_whitelist_exact_match(self):
        """Test finalizer whitelist with exact matching."""
        # Create mock config with whitelist
        mock_config = MagicMock()
        mock_config.enable_finalizer_cleanup = True
        mock_config.finalizer_timeout = timedelta(minutes=5)
        mock_config.finalizer_whitelist = [
            "karpenter.sh/termination",
            "node.kubernetes.io/exclude-from-external-load-balancers",
        ]
        mock_config.finalizer_blacklist = []

        self.client.config = mock_config

        # Create mock node with finalizers
        mock_node = MagicMock()
        mock_node.metadata.finalizers = [
            "karpenter.sh/termination",  # Should be removed (exact match)
            "karpenter.sh/other",  # Should NOT be removed (not exact match)
            "node.kubernetes.io/exclude-from-external-load-balancers",  # Should be removed (exact match)
            "custom.io/finalizer",  # Should NOT be removed (not in whitelist)
        ]

        # Test _is_safe_to_remove_finalizers
        result = self.client._is_safe_to_remove_finalizers(mock_node)
        self.assertTrue(result)  # Should return True because some finalizers match whitelist

        # Test _remove_stuck_finalizers
        self.client._remove_stuck_finalizers(mock_node)

        # Verify patch was called with correct finalizers to keep
        expected_finalizers_to_keep = ["karpenter.sh/other", "custom.io/finalizer"]
        self.client.v1.patch_node.assert_called_once()
        call_args = self.client.v1.patch_node.call_args[1]["body"]
        self.assertEqual(call_args["metadata"]["finalizers"], expected_finalizers_to_keep)

    def test_finalizer_blacklist_exact_match(self):
        """Test finalizer blacklist with exact matching."""
        # Create mock config with blacklist
        mock_config = MagicMock()
        mock_config.enable_finalizer_cleanup = True
        mock_config.finalizer_timeout = timedelta(minutes=5)
        mock_config.finalizer_whitelist = []
        mock_config.finalizer_blacklist = [
            "critical.example.com/finalizer",
            "important.custom.io/finalizer",
        ]

        self.client.config = mock_config

        # Create mock node with finalizers
        mock_node = MagicMock()
        mock_node.metadata.finalizers = [
            "critical.example.com/finalizer",  # Should NOT be removed (exact match in blacklist)
            "critical.example.com/other",  # Should be removed (not exact match)
            "important.custom.io/finalizer",  # Should NOT be removed (exact match in blacklist)
            "safe.io/finalizer",  # Should be removed (not in blacklist)
        ]

        # Test _is_safe_to_remove_finalizers
        result = self.client._is_safe_to_remove_finalizers(mock_node)
        self.assertFalse(result)  # Should return False because blacklisted finalizers are present

    def test_finalizer_blacklist_safe_to_remove(self):
        """Test finalizer blacklist when no blacklisted finalizers are present."""
        # Create mock config with blacklist
        mock_config = MagicMock()
        mock_config.enable_finalizer_cleanup = True
        mock_config.finalizer_timeout = timedelta(minutes=5)
        mock_config.finalizer_whitelist = []
        mock_config.finalizer_blacklist = ["critical.example.com/finalizer"]

        self.client.config = mock_config

        # Create mock node with finalizers (none in blacklist)
        mock_node = MagicMock()
        mock_node.metadata.finalizers = ["safe.io/finalizer", "another.io/finalizer"]

        # Test _is_safe_to_remove_finalizers
        result = self.client._is_safe_to_remove_finalizers(mock_node)
        self.assertTrue(result)  # Should return True because no blacklisted finalizers

        # Test _remove_stuck_finalizers
        self.client._remove_stuck_finalizers(mock_node)

        # Verify all finalizers are removed (none in blacklist)
        expected_finalizers_to_keep = []
        self.client.v1.patch_node.assert_called_once()
        call_args = self.client.v1.patch_node.call_args[1]["body"]
        self.assertEqual(call_args["metadata"]["finalizers"], expected_finalizers_to_keep)

    def test_finalizer_no_whitelist_or_blacklist(self):
        """Test finalizer cleanup when no whitelist or blacklist is configured."""
        # Create mock config with no whitelist/blacklist
        mock_config = MagicMock()
        mock_config.enable_finalizer_cleanup = True
        mock_config.finalizer_timeout = timedelta(minutes=5)
        mock_config.finalizer_whitelist = []
        mock_config.finalizer_blacklist = []

        self.client.config = mock_config

        # Create mock node with finalizers
        mock_node = MagicMock()
        mock_node.metadata.finalizers = ["some.io/finalizer"]

        # Test _is_safe_to_remove_finalizers
        result = self.client._is_safe_to_remove_finalizers(mock_node)
        self.assertFalse(result)  # Should return False for safety when no config

    def test_finalizer_whitelist_no_matches(self):
        """Test finalizer whitelist when no finalizers match."""
        # Create mock config with whitelist
        mock_config = MagicMock()
        mock_config.enable_finalizer_cleanup = True
        mock_config.finalizer_timeout = timedelta(minutes=5)
        mock_config.finalizer_whitelist = ["karpenter.sh/termination"]
        mock_config.finalizer_blacklist = []

        self.client.config = mock_config

        # Create mock node with finalizers that don't match whitelist
        mock_node = MagicMock()
        mock_node.metadata.finalizers = [
            "karpenter.sh/other",  # Similar but not exact match
            "custom.io/finalizer",
        ]

        # Test _is_safe_to_remove_finalizers
        result = self.client._is_safe_to_remove_finalizers(mock_node)
        self.assertFalse(result)  # Should return False because no exact matches

    def test_should_cleanup_finalizers_timeout(self):
        """Test _should_cleanup_finalizers with timeout logic."""
        # Create mock config
        mock_config = MagicMock()
        mock_config.enable_finalizer_cleanup = True
        mock_config.finalizer_timeout = timedelta(minutes=5)
        mock_config.finalizer_whitelist = ["safe.io/finalizer"]
        mock_config.finalizer_blacklist = []

        self.client.config = mock_config

        # Create mock node that has been terminating for longer than timeout
        mock_node = MagicMock()
        mock_node.metadata.deletion_timestamp = datetime.now(timezone.utc) - timedelta(minutes=10)
        mock_node.metadata.finalizers = ["safe.io/finalizer"]

        # Test _should_cleanup_finalizers
        result = self.client._should_cleanup_finalizers(mock_node)
        self.assertTrue(result)  # Should return True because timeout exceeded and safe to remove

    def test_should_cleanup_finalizers_no_timeout(self):
        """Test _should_cleanup_finalizers when timeout not exceeded."""
        # Create mock config
        mock_config = MagicMock()
        mock_config.enable_finalizer_cleanup = True
        mock_config.finalizer_timeout = timedelta(minutes=5)
        mock_config.finalizer_whitelist = ["safe.io/finalizer"]
        mock_config.finalizer_blacklist = []

        self.client.config = mock_config

        # Create mock node that has been terminating for less than timeout
        mock_node = MagicMock()
        mock_node.metadata.deletion_timestamp = datetime.now(timezone.utc) - timedelta(minutes=2)
        mock_node.metadata.finalizers = ["safe.io/finalizer"]

        # Test _should_cleanup_finalizers
        result = self.client._should_cleanup_finalizers(mock_node)
        self.assertFalse(result)  # Should return False because timeout not exceeded

    def test_should_cleanup_finalizers_disabled(self):
        """Test _should_cleanup_finalizers when cleanup is disabled."""
        # Create mock config with cleanup disabled
        mock_config = MagicMock()
        mock_config.enable_finalizer_cleanup = False

        self.client.config = mock_config

        # Create mock node
        mock_node = MagicMock()
        mock_node.metadata.deletion_timestamp = datetime.now(timezone.utc) - timedelta(minutes=10)
        mock_node.metadata.finalizers = ["some.io/finalizer"]

        # Test _should_cleanup_finalizers
        result = self.client._should_cleanup_finalizers(mock_node)
        self.assertFalse(result)  # Should return False because cleanup is disabled


if __name__ == "__main__":
    unittest.main()
