"""
Main NodeReaper class.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

import logging
import sys

from .config import Config
from .kubernetes_client import KubernetesClient
from .node_analyzer import NodeAnalyzer
from .notifier import NotificationManager


class NodeReaper:
    """Main NodeReaper class that orchestrates node cleanup."""

    def __init__(self, config: Config | None = None):
        """Initialize NodeReaper."""
        self.config = config or Config()
        self.logger = self._setup_logging()

        # Initialize components
        self.k8s_client = KubernetesClient(self.config)
        self.node_analyzer = NodeAnalyzer(
            self.config.min_age,
            self.config.deletion_timeout,
            self.config.deletion_taints,
            self.config.protection_annotations,
            self.config.protection_labels,
        )
        self.notifier = NotificationManager(self.config.slack_webhook_url)

    def _setup_logging(self) -> logging.Logger:
        """Configure logging."""
        logging.basicConfig(
            level=getattr(logging, self.config.log_level, logging.INFO),
            format="[%(asctime)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        return logging.getLogger(__name__)

    def run(self) -> None:
        """Run NodeReaper."""
        self.logger.info(
            f"NodeReaper starting (DRY_RUN={self.config.dry_run}, "
            f"MIN_AGE={self.config.min_age})"
        )

        # Test cluster connectivity
        if not self.k8s_client.test_connectivity():
            self.logger.error("Cannot connect to Kubernetes cluster")
            sys.exit(1)

        self.process_nodes()

    def process_nodes(self) -> None:
        """Process all nodes in the cluster."""
        self.logger.info("Starting NodeReaper run...")

        if self.config.node_label_selector:
            selector_str = ",".join(
                [f"{k}={v}" for k, v in self.config.node_label_selector.items()]
            )
            self.logger.info(f"Using node label selector: {selector_str}")
        else:
            self.logger.info("No node label selector specified, processing all nodes")

        try:
            nodes = self.k8s_client.list_nodes(self.config.node_label_selector)
            deleted_count = 0

            for node in nodes:
                node_name = node.metadata.name
                self.logger.debug(f"Processing node: {node_name}")

                # Get pods on this node
                pods = self.k8s_client.list_pods_on_node(node_name)

                # Analyze if node should be deleted
                should_delete, reason = self.node_analyzer.should_delete_node(node, pods)

                if should_delete:
                    if self._delete_node(node, reason):
                        deleted_count += 1

            self.logger.info(f"NodeReaper run completed. Deleted {deleted_count} nodes.")

        except Exception as e:
            self.logger.error(f"Error during node processing: {e}")
            sys.exit(1)

    def _delete_node(self, node, reason: str) -> bool:
        """Delete a node and send notifications."""
        cluster_name = self.config.cluster_name
        node_info = self.node_analyzer.get_node_info(node, cluster_name)

        if self.config.dry_run:
            self.logger.info(
                f"DRY RUN: Would delete node {node_info['name']} "
                f"(cluster: {node_info['cluster']}, age: {node_info['age']}, reason: {reason})"
            )
            return True

        self.logger.info(
            f"Deleting node {node_info['name']} "
            f"(cluster: {node_info['cluster']}, age: {node_info['age']}, reason: {reason})"
        )

        if self.k8s_client.delete_node(node_info["name"]):
            self.notifier.notify_node_deletion(node_info, reason)
            return True

        return False
