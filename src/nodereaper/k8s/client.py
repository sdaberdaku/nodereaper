"""
Kubernetes API client wrapper with error handling and node management operations.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

import logging

from kubernetes import client as k8s
from kubernetes import config as k8s_config
from kubernetes.client import ApiException

from nodereaper.k8s.exception import KubernetesException, handle_k8s_api_exception
from nodereaper.settings import TEST_KUBE_CONTEXT_NAME

logger = logging.getLogger(__name__)


class KubernetesClient:
    """Wrapper for Kubernetes API operations."""

    def __init__(self) -> None:
        """Initialize Kubernetes client."""
        try:
            k8s_config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes config")
        except k8s_config.ConfigException:
            try:
                k8s_config.load_kube_config()
                logger.info("Loaded local Kubernetes config")
                # Verify we are using the expected kube-context for testing
                _, current_context = k8s_config.list_kube_config_contexts()
                if current_context["name"] != TEST_KUBE_CONTEXT_NAME:
                    raise KubernetesException(
                        f"Unexpected kube-context '{current_context['name']}' name"
                    )
            except k8s_config.ConfigException as e:
                raise KubernetesException(
                    f"Failed to load Kubernetes config: {e}. Ensure you have a valid "
                    f"kubeconfig file or are running in a Kubernetes cluster"
                ) from e
            except Exception as e:
                raise KubernetesException(f"Unexpected error loading kube config: {e}") from e

        self.v1: k8s.CoreV1Api = k8s.CoreV1Api()
        logger.info("Kubernetes client initialized")

    @handle_k8s_api_exception
    def list_nodes(self, label_selector: str = "") -> list[k8s.V1Node]:
        """List nodes in the cluster, optionally filtered by labels.

        :param label_selector: Kubernetes label selector string (e.g., "key1=value1,key2=value2")
        :return: List of V1Node objects matching the criteria
        """
        selector_str: str | None = label_selector or None
        nodes: k8s.V1NodeList = self.v1.list_node(label_selector=selector_str)

        filter_msg = f" matching '{label_selector}'" if label_selector else ""
        logger.info(f"Found {len(nodes.items)} nodes{filter_msg}")

        return nodes.items

    @handle_k8s_api_exception
    def list_pods_on_node(self, node_name: str) -> list[k8s.V1Pod]:
        """List all pods running on a specific node.

        :param node_name: Name of the node
        :return: List of pods running on the node
        """
        pods: k8s.V1PodList = self.v1.list_pod_for_all_namespaces(
            field_selector=f"spec.nodeName={node_name}"
        )
        return pods.items

    @handle_k8s_api_exception
    def delete_node(self, node_name: str) -> None:
        """Delete a node from the cluster with force delete.

        :param node_name: Name of the node to delete
        """
        try:
            # Force delete with grace period of 0 seconds
            self.v1.delete_node(name=node_name, grace_period_seconds=0)
            logger.info(f"Deleted node {node_name}")
        except ApiException as e:
            if e.status == 404:
                logger.info(f"Node {node_name} already deleted")
            else:
                raise e

    @handle_k8s_api_exception
    def cleanup_stuck_finalizers(
        self,
        node_name: str,
        finalizers_to_remove: list[str],
        finalizers_to_keep: list[str],
    ) -> None:
        """Remove stuck finalizers from a terminating node.

        :param node_name: Name of the node
        :param finalizers_to_remove: List of finalizers to remove
        :param finalizers_to_keep: List of finalizers to keep
        """
        # Only patch if we have finalizers to remove
        if finalizers_to_remove:
            patch_body = {"metadata": {"finalizers": finalizers_to_keep}}
            try:
                self.v1.patch_node(name=node_name, body=patch_body)
                logger.info(f"Removed stuck finalizers from {node_name}: {finalizers_to_remove}")
            except ApiException as e:
                if e.status == 404:
                    logger.info(f"Node {node_name} already deleted")
                else:
                    raise e
        else:
            logger.info(f"No finalizers to remove from node {node_name}")
