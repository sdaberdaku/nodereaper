"""
Unit tests for main orchestration class, workflow execution, and message formatting.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

from unittest.mock import Mock, patch

import pytest
from kubernetes import client as k8s

from nodereaper.k8s.exception import KubernetesException
from nodereaper.reaper import NodeReaper


class TestNodeReaperInitialization:
    """Test NodeReaper initialization."""

    @patch("nodereaper.reaper.KubernetesClient")
    @patch("nodereaper.reaper.NodeAnalyzer")
    def test_initialization_with_defaults(self, mock_node_analyzer, mock_k8s_client):
        """Test NodeReaper initialization with default values."""
        reaper = NodeReaper()

        assert reaper.dry_run is not None
        assert reaper.enable_finalizer_cleanup is not None
        assert reaper.node_label_selector is not None
        mock_k8s_client.assert_called_once()
        mock_node_analyzer.assert_called_once()

    @patch("nodereaper.reaper.KubernetesClient")
    @patch("nodereaper.reaper.NodeAnalyzer")
    def test_initialization_with_custom_values(self, mock_node_analyzer, mock_k8s_client):
        """Test NodeReaper initialization with custom values."""
        reaper = NodeReaper(
            dry_run=True, enable_finalizer_cleanup=False, node_label_selector="cleanup=enabled"
        )

        assert reaper.dry_run is True
        assert reaper.enable_finalizer_cleanup is False
        assert reaper.node_label_selector == "cleanup=enabled"


class TestNodeReaperExecution:
    """Test NodeReaper execution logic."""

    def setup_method(self):
        """Set up test environment."""
        with patch("nodereaper.reaper.KubernetesClient") as mock_k8s_client, patch(
            "nodereaper.reaper.NodeAnalyzer"
        ) as mock_node_analyzer:
            self.mock_k8s_client_instance = Mock()
            self.mock_node_analyzer_instance = Mock()

            mock_k8s_client.return_value = self.mock_k8s_client_instance
            mock_node_analyzer.return_value = self.mock_node_analyzer_instance

            self.reaper = NodeReaper(
                dry_run=False, enable_finalizer_cleanup=True, node_label_selector="cleanup=enabled"
            )

    def create_mock_node(self, name="test-node", terminating=False):
        """Create a mock Kubernetes node."""
        node = Mock(spec=k8s.V1Node)
        node.metadata = Mock()
        node.metadata.name = name
        return node

    @patch("nodereaper.reaper.send_notification")
    def test_run_calls_process_nodes(self, mock_send_notification):
        """Test that run() calls process_nodes()."""
        self.mock_k8s_client_instance.list_nodes.return_value = []

        self.reaper.run()

        self.mock_k8s_client_instance.list_nodes.assert_called_once_with("cleanup=enabled")

    def test_process_nodes_kubernetes_exception(self):
        """Test process_nodes handles KubernetesException."""
        self.mock_k8s_client_instance.list_nodes.side_effect = KubernetesException("API Error")

        with pytest.raises(KubernetesException):
            self.reaper.process_nodes()

    @patch("nodereaper.reaper.send_notification")
    def test_process_nodes_terminating_node_finalizer_cleanup(self, mock_send_notification):
        """Test processing terminating node with finalizer cleanup."""
        # Setup node
        node = self.create_mock_node("terminating-node")
        self.mock_k8s_client_instance.list_nodes.return_value = [node]

        # Node is terminating
        self.mock_node_analyzer_instance.is_terminating.return_value = True

        # Should cleanup finalizers
        self.mock_node_analyzer_instance.should_cleanup_finalizers.return_value = (
            True,
            "Node stuck terminating",
        )

        # Finalizers to remove/keep
        self.mock_node_analyzer_instance.finalizers_to_remove.return_value = ["stuck.finalizer"]
        self.mock_node_analyzer_instance.finalizers_to_keep.return_value = ["keep.finalizer"]

        # Mock get_node_info
        self.mock_node_analyzer_instance.get_node_info.return_value = {
            "name": "terminating-node",
            "cluster": "test-cluster",
            "age": "1h",
            "instance_type": "m5.large",
            "zone": "us-west-2a",
        }

        self.reaper.process_nodes()

        # Verify finalizer cleanup was called
        self.mock_k8s_client_instance.cleanup_stuck_finalizers.assert_called_once_with(
            node_name="terminating-node",
            finalizers_to_remove=["stuck.finalizer"],
            finalizers_to_keep=["keep.finalizer"],
        )

        # Verify notification was sent
        mock_send_notification.assert_called_once()

    @patch("nodereaper.reaper.send_notification")
    def test_process_nodes_terminating_node_no_cleanup_needed(self, mock_send_notification):
        """Test processing terminating node that doesn't need cleanup."""
        # Setup node
        node = self.create_mock_node("terminating-node")
        self.mock_k8s_client_instance.list_nodes.return_value = [node]

        # Node is terminating
        self.mock_node_analyzer_instance.is_terminating.return_value = True

        # Should not cleanup finalizers
        self.mock_node_analyzer_instance.should_cleanup_finalizers.return_value = (
            False,
            "Timeout not expired",
        )

        self.reaper.process_nodes()

        # Verify no finalizer cleanup was called
        self.mock_k8s_client_instance.cleanup_stuck_finalizers.assert_not_called()

        # Verify no notification was sent
        mock_send_notification.assert_not_called()

    @patch("nodereaper.reaper.send_notification")
    def test_process_nodes_normal_node_should_delete(self, mock_send_notification):
        """Test processing normal node that should be deleted."""
        # Setup node and pods
        node = self.create_mock_node("empty-node")
        pods = []
        self.mock_k8s_client_instance.list_nodes.return_value = [node]
        self.mock_k8s_client_instance.list_pods_on_node.return_value = pods

        # Node is not terminating
        self.mock_node_analyzer_instance.is_terminating.return_value = False

        # Should delete node
        self.mock_node_analyzer_instance.should_delete_node.return_value = (True, "Node is empty")

        # Mock get_node_info
        self.mock_node_analyzer_instance.get_node_info.return_value = {
            "name": "empty-node",
            "cluster": "test-cluster",
            "age": "1h",
            "instance_type": "m5.large",
            "zone": "us-west-2a",
        }

        self.reaper.process_nodes()

        # Verify node deletion was called
        self.mock_k8s_client_instance.delete_node.assert_called_once_with("empty-node")

        # Verify notification was sent
        mock_send_notification.assert_called_once()

    @patch("nodereaper.reaper.send_notification")
    def test_process_nodes_normal_node_should_not_delete(self, mock_send_notification):
        """Test processing normal node that should not be deleted."""
        # Setup node and pods
        node = self.create_mock_node("protected-node")
        pods = []
        self.mock_k8s_client_instance.list_nodes.return_value = [node]
        self.mock_k8s_client_instance.list_pods_on_node.return_value = pods

        # Node is not terminating
        self.mock_node_analyzer_instance.is_terminating.return_value = False

        # Should not delete node
        self.mock_node_analyzer_instance.should_delete_node.return_value = (
            False,
            "Node has protection annotation",
        )

        self.reaper.process_nodes()

        # Verify no node deletion was called
        self.mock_k8s_client_instance.delete_node.assert_not_called()

        # Verify no notification was sent
        mock_send_notification.assert_not_called()

    @patch("nodereaper.reaper.send_notification")
    def test_process_nodes_dry_run_mode(self, mock_send_notification):
        """Test processing nodes in dry run mode."""
        # Enable dry run
        self.reaper.dry_run = True

        # Setup node
        node = self.create_mock_node("test-node")
        pods = []
        self.mock_k8s_client_instance.list_nodes.return_value = [node]
        self.mock_k8s_client_instance.list_pods_on_node.return_value = pods

        # Node is not terminating and should be deleted
        self.mock_node_analyzer_instance.is_terminating.return_value = False
        self.mock_node_analyzer_instance.should_delete_node.return_value = (True, "Node is empty")

        # Mock get_node_info
        self.mock_node_analyzer_instance.get_node_info.return_value = {
            "name": "test-node",
            "cluster": "test-cluster",
            "age": "1h",
            "instance_type": "m5.large",
            "zone": "us-west-2a",
        }

        self.reaper.process_nodes()

        # Verify no actual deletion was called
        self.mock_k8s_client_instance.delete_node.assert_not_called()

        # Verify notification was still sent (for dry run)
        mock_send_notification.assert_called_once()

    @patch("nodereaper.reaper.send_notification")
    def test_process_nodes_finalizer_cleanup_disabled(self, mock_send_notification):
        """Test processing terminating node with finalizer cleanup disabled."""
        # Disable finalizer cleanup
        self.reaper.enable_finalizer_cleanup = False

        # Setup node
        node = self.create_mock_node("terminating-node")
        self.mock_k8s_client_instance.list_nodes.return_value = [node]

        # Node is terminating and should cleanup finalizers
        self.mock_node_analyzer_instance.is_terminating.return_value = True
        self.mock_node_analyzer_instance.should_cleanup_finalizers.return_value = (
            True,
            "Node stuck terminating",
        )

        # Mock get_node_info
        self.mock_node_analyzer_instance.get_node_info.return_value = {
            "name": "terminating-node",
            "cluster": "test-cluster",
            "age": "1h",
            "instance_type": "m5.large",
            "zone": "us-west-2a",
        }

        self.reaper.process_nodes()

        # Verify no finalizer cleanup was called
        self.mock_k8s_client_instance.cleanup_stuck_finalizers.assert_not_called()

        # Verify notification was still sent (for dry run notification)
        mock_send_notification.assert_called_once()

    @patch("nodereaper.reaper.send_notification")
    def test_process_nodes_deletion_error(self, mock_send_notification):
        """Test processing node when deletion fails."""
        # Setup node
        node = self.create_mock_node("error-node")
        pods = []
        self.mock_k8s_client_instance.list_nodes.return_value = [node]
        self.mock_k8s_client_instance.list_pods_on_node.return_value = pods

        # Node should be deleted but deletion fails
        self.mock_node_analyzer_instance.is_terminating.return_value = False
        self.mock_node_analyzer_instance.should_delete_node.return_value = (True, "Node is empty")
        self.mock_k8s_client_instance.delete_node.side_effect = KubernetesException("Delete failed")

        # Mock get_node_info
        self.mock_node_analyzer_instance.get_node_info.return_value = {
            "name": "error-node",
            "cluster": "test-cluster",
            "age": "1h",
            "instance_type": "m5.large",
            "zone": "us-west-2a",
        }

        self.reaper.process_nodes()

        # Verify deletion was attempted
        self.mock_k8s_client_instance.delete_node.assert_called_once_with("error-node")

        # Verify error notification was sent
        mock_send_notification.assert_called_once()
        call_args = mock_send_notification.call_args[0][0]
        assert ":warning:" in call_args
        assert "Delete failed" in call_args

    @patch("nodereaper.reaper.send_notification")
    def test_process_nodes_finalizer_cleanup_error(self, mock_send_notification):
        """Test processing node when finalizer cleanup fails."""
        # Setup node
        node = self.create_mock_node("stuck-node")
        self.mock_k8s_client_instance.list_nodes.return_value = [node]

        # Node is terminating and should cleanup finalizers
        self.mock_node_analyzer_instance.is_terminating.return_value = True
        self.mock_node_analyzer_instance.should_cleanup_finalizers.return_value = (
            True,
            "Node stuck terminating",
        )
        self.mock_node_analyzer_instance.finalizers_to_remove.return_value = ["stuck.finalizer"]
        self.mock_node_analyzer_instance.finalizers_to_keep.return_value = []

        # Finalizer cleanup fails
        self.mock_k8s_client_instance.cleanup_stuck_finalizers.side_effect = KubernetesException(
            "Cleanup failed"
        )

        # Mock get_node_info
        self.mock_node_analyzer_instance.get_node_info.return_value = {
            "name": "stuck-node",
            "cluster": "test-cluster",
            "age": "1h",
            "instance_type": "m5.large",
            "zone": "us-west-2a",
        }

        self.reaper.process_nodes()

        # Verify cleanup was attempted
        self.mock_k8s_client_instance.cleanup_stuck_finalizers.assert_called_once()

        # Verify error notification was sent
        mock_send_notification.assert_called_once()
        call_args = mock_send_notification.call_args[0][0]
        assert ":warning:" in call_args
        assert "Cleanup failed" in call_args


class TestNodeReaperMessageFormatting:
    """Test NodeReaper message formatting."""

    def setup_method(self):
        """Set up test environment."""
        with patch("nodereaper.reaper.KubernetesClient"), patch(
            "nodereaper.reaper.NodeAnalyzer"
        ) as mock_node_analyzer:
            self.mock_node_analyzer_instance = Mock()
            mock_node_analyzer.return_value = self.mock_node_analyzer_instance

            self.reaper = NodeReaper()

    def create_mock_node(self, name="test-node"):
        """Create a mock Kubernetes node."""
        node = Mock(spec=k8s.V1Node)
        node.metadata = Mock()
        node.metadata.name = name
        return node

    def test_format_message_delete_success(self):
        """Test formatting message for successful deletion."""
        node = self.create_mock_node("test-node")
        self.mock_node_analyzer_instance.get_node_info.return_value = {
            "name": "test-node",
            "cluster": "test-cluster",
            "age": "1h",
            "instance_type": "m5.large",
            "zone": "us-west-2a",
        }

        message = self.reaper._format_message(
            node=node, reason="Node is empty", error_msg=None, dry_run=False, action="delete"
        )

        assert ":skull_and_crossbones:" in message
        assert "delete Node" in message
        assert "test-node" in message
        assert "test-cluster" in message
        assert "Node is empty" in message

    def test_format_message_cleanup_success(self):
        """Test formatting message for successful finalizer cleanup."""
        node = self.create_mock_node("stuck-node")
        self.mock_node_analyzer_instance.get_node_info.return_value = {
            "name": "stuck-node",
            "cluster": "test-cluster",
            "age": "2h",
            "instance_type": "m5.large",
            "zone": "us-west-2a",
        }

        message = self.reaper._format_message(
            node=node,
            reason="Node stuck terminating",
            error_msg=None,
            dry_run=False,
            action="cleanup",
        )

        assert ":broom:" in message
        assert "cleanup Node" in message
        assert "stuck-node" in message
        assert "Node stuck terminating" in message

    def test_format_message_dry_run(self):
        """Test formatting message for dry run."""
        node = self.create_mock_node("test-node")
        self.mock_node_analyzer_instance.get_node_info.return_value = {
            "name": "test-node",
            "cluster": "test-cluster",
            "age": "1h",
            "instance_type": "m5.large",
            "zone": "us-west-2a",
        }

        message = self.reaper._format_message(
            node=node, reason="Node is empty", error_msg=None, dry_run=True, action="delete"
        )

        assert ":information_source:" in message
        assert "would delete Node" in message
        assert "test-node" in message

    def test_format_message_error(self):
        """Test formatting message for error."""
        node = self.create_mock_node("error-node")
        self.mock_node_analyzer_instance.get_node_info.return_value = {
            "name": "error-node",
            "cluster": "test-cluster",
            "age": "1h",
            "instance_type": "m5.large",
            "zone": "us-west-2a",
        }

        message = self.reaper._format_message(
            node=node,
            reason="Node is empty",
            error_msg="Permission denied",
            dry_run=False,
            action="delete",
        )

        assert ":warning:" in message
        assert "failed to delete Node" in message
        assert "Permission denied" in message
        assert "error-node" in message
