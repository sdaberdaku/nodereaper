#!/bin/bash

# Script to test Helm chart deployment and functionality
# Usage: ./scripts/test-helm-chart.sh [cluster-name]

set -e

CLUSTER_NAME="${1:-nodereaper-test}"
IMAGE_TAG="${IMAGE_TAG:-test}"
IMAGE_REPO="${IMAGE_REPO:-ghcr.io/sdaberdaku/nodereaper}"

echo "🧪 Testing Helm chart deployment..."

# Function to test with a specific label selector
test_with_selector() {
    local selector="$1"
    local job_suffix=$(echo "$selector" | tr '=' '-' | tr '.' '-' | tr ',' '-')
    local job_name="nodereaper-test-$job_suffix"

    echo "🔍 Testing with selector: $selector"

    # Update Helm chart with new selector
    helm upgrade nodereaper helm/ -n nodereaper --create-namespace \
        --set image.repository="$IMAGE_REPO" \
        --set image.tag="$IMAGE_TAG" \
        --set image.pullPolicy=Never \
        --set config.dryRun=true \
        --set config.logLevel=INFO \
        --set config.nodeMinAge=1s \
        --set config.nodeLabelSelector[0]="$selector"

    # Create and wait for job
    kubectl create job --from=cronjob/nodereaper "$job_name" -n nodereaper
    kubectl wait --for=condition=complete "job/$job_name" -n nodereaper --timeout=60s

    # Check logs
    echo "📋 Job logs:"
    kubectl logs -n nodereaper -l "job-name=$job_name" | grep -E "(Found.*nodes|Would delete|completed|NodeReaper starting)"

    echo "✅ Test with selector '$selector' completed"
    echo ""
}

# Function to verify Helm deployment
verify_deployment() {
    echo "🔍 Verifying Helm deployment..."

    # Check resources
    kubectl get cronjob nodereaper -n nodereaper
    kubectl get serviceaccount nodereaper -n nodereaper

    # Check RBAC (these might be cluster-scoped)
    if kubectl get clusterrole nodereaper &>/dev/null; then
        echo "✅ ClusterRole found"
    else
        echo "⚠️  ClusterRole not found (might be expected)"
    fi

    if kubectl get clusterrolebinding nodereaper &>/dev/null; then
        echo "✅ ClusterRoleBinding found"
    else
        echo "⚠️  ClusterRoleBinding not found (might be expected)"
    fi

    echo "✅ Deployment verification completed"
    echo ""
}

# Main execution
main() {
    # Check if cluster is available
    if ! kubectl cluster-info &>/dev/null; then
        echo "❌ Cannot connect to Kubernetes cluster"
        echo "💡 Make sure cluster '$CLUSTER_NAME' is running"
        exit 1
    fi

    # Check if current context matches expected cluster name
    current_context=$(kubectl config current-context 2>/dev/null || echo "")
    expected_context="kind-${CLUSTER_NAME}"
    if [[ "$current_context" != "$expected_context" ]]; then
        echo "❌ Wrong cluster context. Expected: $expected_context, Current: $current_context"
        echo "💡 Switch context with: kubectl config use-context $expected_context"
        exit 1
    fi

    echo "📋 Using cluster: $current_context"
    echo "📋 Using image: $IMAGE_REPO:$IMAGE_TAG"
    echo ""

    # Build and load Docker image if needed
    if [[ "$IMAGE_TAG" == "test" ]]; then
        echo "🔨 Building Docker image..."
        docker build -t "$IMAGE_REPO:$IMAGE_TAG" .

        echo "📦 Loading image into kind cluster..."
        kind load docker-image "$IMAGE_REPO:$IMAGE_TAG" --name "$CLUSTER_NAME"
        echo ""
    fi

    # Install Helm chart
    echo "📦 Installing Helm chart..."
    helm install nodereaper helm/ -n nodereaper --create-namespace \
        --set image.repository="$IMAGE_REPO" \
        --set image.tag="$IMAGE_TAG" \
        --set image.pullPolicy=Never \
        --set config.dryRun=true \
        --set config.logLevel=INFO \
        --set config.nodeMinAge=1s \
        --set config.nodeLabelSelector[0]="cleanup-enabled=true"

    echo "✅ Helm chart installed"
    echo ""

    # Verify deployment
    verify_deployment

    # Test with different selectors
    test_with_selector "cleanup-enabled=true"
    test_with_selector "instance-type=m5.large"
    test_with_selector "instance-type=m5.xlarge"

    # Show node protection verification
    echo "🛡️  Verifying node protection..."
    echo "Nodes with NodeReaper jobs should be protected from deletion:"
    kubectl get pods -A -o wide | grep nodereaper-test || echo "No NodeReaper test pods found"

    # Run Helm tests
    echo ""
    echo "🧪 Running Helm tests..."
    if helm test nodereaper -n nodereaper; then
        echo "✅ Helm tests passed"
    else
        echo "❌ Helm tests failed"
        echo "📋 Checking test pod logs..."
        kubectl logs -n nodereaper -l "app.kubernetes.io/name=nodereaper" --tail=50 || true
        return 1
    fi

    echo ""
    echo "🎉 Helm chart testing completed successfully!"
    echo ""
    echo "💡 To clean up:"
    echo "   scripts/cleanup.sh --helm-only"
}

# Handle command line arguments
case "${1:-}" in
    "--help"|"-h")
        echo "Usage: $0 [cluster-name]"
        echo ""
        echo "Test Helm chart deployment and functionality"
        echo ""
        echo "Arguments:"
        echo "  cluster-name    Name of the kind cluster (default: nodereaper-test)"
        echo ""
        echo "Environment variables:"
        echo "  IMAGE_TAG       Docker image tag to use (default: test)"
        echo "  IMAGE_REPO      Docker image repository (default: ghcr.io/sdaberdaku/nodereaper)"
        echo ""
        echo "Examples:"
        echo "  $0                           # Use default cluster"
        echo "  $0 my-test-cluster          # Use specific cluster"
        echo "  IMAGE_TAG=latest $0         # Use latest image"
        exit 0
        ;;
esac

# Run main function
main "$@"
