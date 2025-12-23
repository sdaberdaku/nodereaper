"""Tests for main reaper module."""

import unittest
from unittest.mock import MagicMock, patch

from nodereaper.config import Config
from nodereaper.reaper import NodeReaper


class TestNodeReaper(unittest.TestCase):
    """Test cases for NodeReaper class."""

    def setUp(self):
        """Set up test environment."""
        # Create a test config
        self.config = Config()
        self.config.dry_run = True
        self.config.log_level = "DEBUG"

        # Mock all dependencies
        with patch("nodereaper.reaper.KubernetesClient") as mock_k8s:
            with patch("nodereaper.reaper.NodeAnalyzer") as mock_analyzer:
                with patch("nodereaper.reaper.NotificationManager") as mock_notifier:
                    self.reaper = NodeReaper(self.config)

                    # Set up mocks
                    self.mock_k8s = mock_k8s.return_value
                    self.mock_analyzer = mock_analyzer.return_value
                    self.mock_notifier = mock_notifier.return_value

    def test_initialization(self):
        """Test NodeReaper initialization."""
        self.assertEqual(self.reaper.config, self.config)
        self.assertIsNotNone(self.reaper.logger)

    def test_connectivity_failure(self):
        """Test behavior when Kubernetes connectivity fails."""
        self.mock_k8s.test_connectivity.return_value = False

        with self.assertRaises(SystemExit):
            self.reaper.run()

    def test_process_nodes_success(self):
        """Test successful node processing."""
        # Mock connectivity
        self.mock_k8s.test_connectivity.return_value = True

        # Mock nodes and pods
        mock_node1 = MagicMock()
        mock_node1.metadata.name = "node1"
        mock_node2 = MagicMock()
        mock_node2.metadata.name = "node2"

        self.mock_k8s.list_nodes.return_value = [mock_node1, mock_node2]
        self.mock_k8s.list_pods_on_node.return_value = []

        # Mock analyzer decisions
        self.mock_analyzer.should_delete_node.side_effect = [
            (True, "empty"),  # node1 should be deleted
            (False, ""),  # node2 should not be deleted
        ]

        # Mock node info
        self.mock_analyzer.get_node_info.return_value = {
            "name": "node1",
            "age": "15m",
            "cluster": "test-cluster",
            "instance_type": "m5.large",
            "zone": "us-west-2a",
        }

        # Mock successful deletion
        self.mock_k8s.delete_node.return_value = True

        # Run the process
        self.reaper.process_nodes()

        # Verify calls
        self.mock_k8s.list_nodes.assert_called_once()
        self.assertEqual(self.mock_k8s.list_pods_on_node.call_count, 2)
        self.assertEqual(self.mock_analyzer.should_delete_node.call_count, 2)

    def test_dry_run_mode(self):
        """Test dry run mode behavior."""
        self.config.dry_run = True

        mock_node = MagicMock()
        mock_node.metadata.name = "test-node"

        self.mock_analyzer.get_node_info.return_value = {
            "name": "test-node",
            "age": "15m",
            "cluster": "test-cluster",
            "instance_type": "m5.large",
            "zone": "us-west-2a",
        }

        result = self.reaper._delete_node(mock_node, "empty")

        self.assertTrue(result)
        # Should not call actual delete or notifications in dry run
        self.mock_k8s.delete_node.assert_not_called()
        self.mock_notifier.notify_node_deletion.assert_not_called()

    def test_actual_deletion(self):
        """Test actual node deletion (not dry run)."""
        self.config.dry_run = False

        mock_node = MagicMock()
        mock_node.metadata.name = "test-node"

        self.mock_analyzer.get_node_info.return_value = {
            "name": "test-node",
            "age": "15m",
            "cluster": "test-cluster",
            "instance_type": "m5.large",
            "zone": "us-west-2a",
        }

        self.mock_k8s.delete_node.return_value = True

        result = self.reaper._delete_node(mock_node, "empty")

        self.assertTrue(result)
        self.mock_k8s.delete_node.assert_called_once_with("test-node")
        self.mock_notifier.notify_node_deletion.assert_called_once()

    def test_failed_deletion(self):
        """Test failed node deletion."""
        self.config.dry_run = False

        mock_node = MagicMock()
        mock_node.metadata.name = "test-node"

        self.mock_analyzer.get_node_info.return_value = {
            "name": "test-node",
            "age": "15m",
            "cluster": "test-cluster",
            "instance_type": "m5.large",
            "zone": "us-west-2a",
        }

        self.mock_k8s.delete_node.return_value = False

        result = self.reaper._delete_node(mock_node, "empty")

        self.assertFalse(result)
        self.mock_notifier.notify_node_deletion.assert_not_called()


if __name__ == "__main__":
    unittest.main()
