"""
NodeReaper orchestration class for managing node cleanup workflows.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

import logging
from typing import Literal

from kubernetes import client as k8s

from nodereaper.k8s import KubernetesClient, NodeAnalyzer, PrometheusClient
from nodereaper.k8s.exception import KubernetesException
from nodereaper.notification import send_notification
from nodereaper.settings import (
    DRY_RUN,
    ENABLE_FINALIZER_CLEANUP,
    NODE_LABEL_SELECTOR,
    PROMETHEUS_ENABLED,
)

logger = logging.getLogger(__name__)


class NodeReaper:
    """Main NodeReaper class that orchestrates node cleanup."""

    def __init__(
        self,
        dry_run: bool = None,
        enable_finalizer_cleanup: bool = None,
        node_label_selector: str = None,
        prometheus_enabled: bool = None,
    ) -> None:
        """Initialize NodeReaper.

        :param dry_run: Enable dry-run mode (no actual deletions)
        :param enable_finalizer_cleanup: Enable finalizer cleanup for stuck nodes
        :param node_label_selector: Label selector to filter nodes
        """
        self.dry_run = DRY_RUN if dry_run is None else dry_run
        self.prometheus_enabled = (
            PROMETHEUS_ENABLED if prometheus_enabled is None else prometheus_enabled
        )
        self.enable_finalizer_cleanup = (
            ENABLE_FINALIZER_CLEANUP
            if enable_finalizer_cleanup is None
            else enable_finalizer_cleanup
        )
        self.node_label_selector = (
            NODE_LABEL_SELECTOR if node_label_selector is None else node_label_selector
        )
        # Initialize components
        self.k8s_client = KubernetesClient()
        self.node_analyzer = NodeAnalyzer()
        self.prometheus_client = PrometheusClient() if self.prometheus_enabled else None
        logger.info(
            f"NodeReaper initialized with "
            f"dry_run={self.dry_run}, "
            f"enable_finalizer_cleanup={self.enable_finalizer_cleanup}, "
            f"node_label_selector={self.node_label_selector}, "
            f"prometheus_enabled={self.prometheus_enabled}"
        )

    def run(self) -> None:
        """Run NodeReaper."""
        logger.info("Starting NodeReaper run...")
        self.process_nodes()
        logger.info("Finished NodeReaper run.")

    def process_nodes(self) -> None:
        """Process all nodes in the cluster."""
        notifications = []

        if self.node_label_selector:
            logger.info(f"Using node label selector: {self.node_label_selector}")
        else:
            logger.info("No node label selector specified, processing all nodes")

        non_empty_nodes = (
            self.prometheus_client.get_non_empty_nodes() if self.prometheus_enabled else set()
        )
        # Without the Prometheus lookback a node that is briefly empty between workloads
        # would look idle, so delete nothing until Prometheus answers again
        skip_deletions = non_empty_nodes is None
        if skip_deletions:
            logger.warning("Prometheus query failed, skipping node deletions in this run")
        try:
            nodes = self.k8s_client.list_nodes(self.node_label_selector)
        except KubernetesException as e:
            logger.exception(f"KubernetesException during node listing: {e}")
            raise e

        try:
            for node in nodes:
                try:
                    message = self._process_node(node, non_empty_nodes or set(), skip_deletions)
                except KubernetesException as e:
                    logger.exception(f"Failed to process node '{node.metadata.name}': {e}")
                    continue
                if message:
                    notifications.append(message)
        finally:
            # Report what was already done even if a later node failed unexpectedly
            if notifications:
                send_notification("\n\n".join(notifications))

    def _process_node(
        self, node: k8s.V1Node, non_empty_nodes: set[str], skip_deletions: bool
    ) -> str | None:
        """Clean up or delete one node if it qualifies.

        :param node: Kubernetes node object
        :param non_empty_nodes: Nodes that recently had non-DaemonSet Pods (per Prometheus)
        :param skip_deletions: Do not delete nodes in this run
        :return: Notification message, or None if nothing was done
        """
        node_name = node.metadata.name
        logger.debug(f"Processing node: {node_name}")
        if self.node_analyzer.is_terminating(node):
            logger.debug(f"Node {node_name} is in terminating state")
            if not self.enable_finalizer_cleanup:
                return None
            # Analyze if finalizers should be cleaned up
            should_cleanup, reason = self.node_analyzer.should_cleanup_finalizers(node)
            logger.debug(
                f"Node: {node_name}, should_cleanup: '{should_cleanup}', reason: '{reason}'"
            )
            if not should_cleanup:
                return None
            error_msg = None
            if not self.dry_run:
                try:
                    self.k8s_client.cleanup_stuck_finalizers(
                        node_name=node_name,
                        node_uid=node.metadata.uid,
                        finalizers_to_remove=self.node_analyzer.finalizers_to_remove(node),
                        finalizers_to_keep=self.node_analyzer.finalizers_to_keep(node),
                    )
                except KubernetesException as e:
                    logger.exception(f"Failed to cleanup node finalizers '{node_name}': {e}")
                    error_msg = str(e)
            return self._format_message(
                node=node,
                reason=reason,
                error_msg=error_msg,
                dry_run=self.dry_run,
                action="cleanup",
            )

        logger.debug(f"Node {node_name} is not in terminating state")
        if skip_deletions:
            return None
        # Get pods on this node
        pods = self.k8s_client.list_pods_on_node(node_name)
        # Analyze if node should be deleted
        if node_name in non_empty_nodes:
            should_delete, reason = (
                False,
                "Node recently had non-DaemonSet Pods (per Prometheus data)",
            )
        else:
            should_delete, reason = self.node_analyzer.should_delete_node(node, pods)
        logger.debug(f"Node: {node_name}, should_delete: '{should_delete}', reason: '{reason}'")
        if not should_delete:
            return None
        error_msg = None
        if not self.dry_run:
            try:
                self.k8s_client.delete_node(node_name)
            except KubernetesException as e:
                logger.exception(f"Failed to delete node '{node_name}': {e}")
                error_msg = str(e)
        return self._format_message(
            node=node,
            reason=reason,
            error_msg=error_msg,
            dry_run=self.dry_run,
            action="delete",
        )

    def _format_message(
        self,
        node: k8s.V1Node,
        reason: str,
        error_msg: str,
        dry_run: bool,
        action: Literal["cleanup", "delete"],
    ) -> str:
        """Format notification message for node actions.

        :param node: Kubernetes node object
        :param reason: Reason for the action
        :param error_msg: Error message if action failed
        :param dry_run: Whether this is a dry-run
        :param action: Type of action (cleanup or delete)
        :return: Formatted message string
        """
        node_info = self.node_analyzer.get_node_info(node)

        if error_msg:
            icon = ":warning:"
            verb = f"failed to {action} Node, error {error_msg}"
        elif dry_run:
            icon = ":information_source:"
            verb = f"would {action} Node"
        else:
            icon = ":skull_and_crossbones:" if action == "delete" else ":broom:"
            verb = f"{action} Node"

        return (
            f"{icon} NodeReaper {verb} \n"
            f"> Node: `{node_info['name']}`\n"
            f"> Cluster: {node_info['cluster']}\n"
            f"> Age: {node_info['age']}\n"
            f"> Instance Type: {node_info['instance_type']}\n"
            f"> Zone: {node_info['zone']}\n"
            f"> Reason: {reason}"
        )
