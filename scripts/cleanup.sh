#!/bin/bash

# Cleanup script for NodeReaper development and testing
# Usage: ./scripts/cleanup.sh [options]

set -e

CLUSTER_NAME="${CLUSTER_NAME:-nodereaper-test}"
NAMESPACE="${NAMESPACE:-nodereaper}"
HELM_RELEASE="${HELM_RELEASE:-nodereaper}"

# Function to show usage
show_usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Cleanup NodeReaper development and testing resources"
    echo ""
    echo "Options:"
    echo "  --helm-only        Only cleanup Helm release"
    echo "  --cluster-only     Only cleanup kind cluster"
    echo "  --all              Cleanup everything (default)"
    echo "  --help, -h         Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  CLUSTER_NAME       Name of the kind cluster (default: nodereaper-test)"
    echo "  NAMESPACE          Kubernetes namespace (default: nodereaper)"
    echo "  HELM_RELEASE       Helm release name (default: nodereaper)"
    echo ""
    echo "Examples:"
    echo "  $0                           # Clean up everything"
    echo "  $0 --helm-only              # Only uninstall Helm release"
    echo "  $0 --cluster-only           # Only delete kind cluster"
    echo "  CLUSTER_NAME=my-test $0     # Use custom cluster name"
}

# Function to check if we're connected to the right cluster
check_cluster() {
    # Check if kubectl is available and cluster is reachable
    if ! kubectl cluster-info &> /dev/null; then
        echo "❌ Kubernetes cluster is not available"
        return 1
    fi

    # Check if current context matches expected cluster name
    current_context=$(kubectl config current-context 2>/dev/null || echo "")
    if [[ -z "$current_context" ]]; then
        echo "❌ No current Kubernetes context set"
        return 1
    fi

    # For kind clusters, the context name is "kind-{cluster-name}"
    expected_context="kind-${CLUSTER_NAME}"
    if [[ "$current_context" != "$expected_context" ]]; then
        echo "❌ Wrong cluster context. Expected: $expected_context, Current: $current_context"
        echo "💡 Switch context with: kubectl config use-context $expected_context"
        return 1
    fi

    echo "✅ Connected to correct cluster: $CLUSTER_NAME"
    return 0
}

# Function to cleanup Helm release
cleanup_helm() {
    echo "🧹 Cleaning up Helm release..."

    # Verify we're connected to the right cluster before making changes
    if ! check_cluster; then
        echo "❌ Aborting cleanup - not connected to the correct cluster"
        exit 1
    fi

    if helm list -n "$NAMESPACE" | grep -q "$HELM_RELEASE"; then
        echo "📦 Uninstalling Helm release '$HELM_RELEASE' from namespace '$NAMESPACE'..."
        helm uninstall "$HELM_RELEASE" -n "$NAMESPACE" || true
        echo "✅ Helm release uninstalled"
    else
        echo "ℹ️  No Helm release '$HELM_RELEASE' found in namespace '$NAMESPACE'"
    fi

    # Clean up any test jobs that might be left behind
    echo "🧹 Cleaning up test jobs..."
    kubectl delete jobs -n "$NAMESPACE" -l "app.kubernetes.io/name=nodereaper" --ignore-not-found=true || true

    # Clean up namespace if it's empty and not default namespaces
    if [[ "$NAMESPACE" != "default" && "$NAMESPACE" != "kube-system" && "$NAMESPACE" != "kube-public" ]]; then
        echo "🧹 Checking if namespace '$NAMESPACE' can be cleaned up..."
        RESOURCES=$(kubectl get all -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l || echo "0")
        if [[ "$RESOURCES" -eq 0 ]]; then
            echo "📦 Deleting empty namespace '$NAMESPACE'..."
            kubectl delete namespace "$NAMESPACE" --ignore-not-found=true || true
        else
            echo "ℹ️  Namespace '$NAMESPACE' still has resources, keeping it"
        fi
    fi
}

# Function to cleanup kind cluster
cleanup_cluster() {
    echo "🧹 Cleaning up kind cluster..."

    if kind get clusters | grep -q "^$CLUSTER_NAME$"; then
        echo "📦 Deleting kind cluster '$CLUSTER_NAME'..."
        kind delete cluster --name "$CLUSTER_NAME" || true
        echo "✅ Kind cluster deleted"
    else
        echo "ℹ️  No kind cluster '$CLUSTER_NAME' found"
    fi
}

# Function to cleanup everything
cleanup_all() {
    echo "🧹 Starting complete cleanup..."
    cleanup_helm
    cleanup_cluster
    echo "✅ Complete cleanup finished"
}

# Main execution
main() {
    case "${1:-}" in
        "--helm-only")
            cleanup_helm
            ;;
        "--cluster-only")
            cleanup_cluster
            ;;
        "--all"|"")
            cleanup_all
            ;;
        "--help"|"-h")
            show_usage
            exit 0
            ;;
        *)
            echo "❌ Unknown option: $1"
            echo ""
            show_usage
            exit 1
            ;;
    esac

    echo ""
    echo "🎉 Cleanup completed successfully!"
}

# Run main function with all arguments
main "$@"
