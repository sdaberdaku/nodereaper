#!/bin/bash

# Script to test Helm chart deployment and functionality
# Usage: ./scripts/test-helm-chart.sh [cluster-name]

set -euo pipefail

CLUSTER_NAME="${1:-nodereaper-test}"
IMAGE_TAG="${IMAGE_TAG:-test}"
IMAGE_REPO="${IMAGE_REPO:-ghcr.io/sdaberdaku/nodereaper}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if cluster is available and has the expected name
check_cluster() {
    log_info "Checking cluster availability..."

    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        log_info "Make sure cluster '$CLUSTER_NAME' is running"
        return 1
    fi

    # Check if we're using the expected context
    local current_context
    current_context=$(kubectl config current-context 2>/dev/null || echo "")
    local expected_context="kind-${CLUSTER_NAME}"

    if [[ "$current_context" != "$expected_context" ]]; then
        log_error "Wrong cluster context. Expected: $expected_context, Current: $current_context"
        log_info "Switch context with: kubectl config use-context $expected_context"
        return 1
    fi

    log_success "Using cluster: $current_context"
    return 0
}

# Function to test with a specific label selector
test_with_selector() {
    local selector="$1"
    local job_suffix=$(echo "$selector" | tr '=' '-' | tr '.' '-' | tr ',' '-')
    local job_name="nodereaper-test-$job_suffix"

    log_info "Testing with selector: $selector"

    # Parse selector into key=value format for map
    local key=$(echo "$selector" | cut -d'=' -f1)
    local value=$(echo "$selector" | cut -d'=' -f2-)

    # Update Helm chart with new selector
    helm upgrade nodereaper "$PROJECT_ROOT/helm" -n nodereaper \
        --set image.repository="$IMAGE_REPO" \
        --set image.tag="$IMAGE_TAG" \
        --set image.pullPolicy=Never \
        --set config.dryRun=true \
        --set config.logLevel=INFO \
        --set config.enableJsonLogs=false \
        --set config.nodeMinAge=1s \
        --set "config.nodeLabelSelector.$key=$value" \
        --wait

    # Create and wait for job
    kubectl create job --from=cronjob/nodereaper "$job_name" -n nodereaper

    # Wait for job completion with timeout
    if kubectl wait --for=condition=complete "job/$job_name" -n nodereaper --timeout=120s; then
        log_success "Job completed successfully"
    else
        log_warning "Job did not complete within timeout, checking status..."
        kubectl describe job "$job_name" -n nodereaper
    fi

    # Check logs
    log_info "Job logs:"
    kubectl logs -n nodereaper -l "job-name=$job_name" --tail=50 | grep -E "(Found.*nodes|Would delete|completed|NodeReaper starting|Processing node)" || true

    # Clean up job
    kubectl delete job "$job_name" -n nodereaper --ignore-not-found=true

    log_success "Test with selector '$selector' completed"
}

# Function to verify Helm deployment
verify_deployment() {
    log_info "Verifying Helm deployment..."

    # Check CronJob
    if kubectl get cronjob nodereaper -n nodereaper &>/dev/null; then
        log_success "CronJob found"
    else
        log_error "CronJob not found"
        return 1
    fi

    # Check ServiceAccount
    if kubectl get serviceaccount nodereaper -n nodereaper &>/dev/null; then
        log_success "ServiceAccount found"
    else
        log_error "ServiceAccount not found"
        return 1
    fi

    # Check RBAC (these are cluster-scoped)
    if kubectl get clusterrole nodereaper &>/dev/null; then
        log_success "ClusterRole found"
    else
        log_warning "ClusterRole not found"
    fi

    if kubectl get clusterrolebinding nodereaper &>/dev/null; then
        log_success "ClusterRoleBinding found"
    else
        log_warning "ClusterRoleBinding not found"
    fi

    log_success "Deployment verification completed"
}

# Build and load Docker image
build_and_load_image() {
    if [[ "$IMAGE_TAG" == "test" ]]; then
        log_info "Building Docker image..."
        cd "$PROJECT_ROOT"
        docker build -t "$IMAGE_REPO:$IMAGE_TAG" .

        log_info "Loading image into kind cluster..."
        kind load docker-image "$IMAGE_REPO:$IMAGE_TAG" --name "$CLUSTER_NAME"
        log_success "Image loaded successfully"
    else
        log_info "Using existing image: $IMAGE_REPO:$IMAGE_TAG"
    fi
}

# Install Helm chart
install_helm_chart() {
    log_info "Installing Helm chart..."

    # Create namespace if it doesn't exist
    kubectl create namespace nodereaper --dry-run=client -o yaml | kubectl apply -f -

    helm upgrade --install nodereaper "$PROJECT_ROOT/helm" -n nodereaper \
        --set image.repository="$IMAGE_REPO" \
        --set image.tag="$IMAGE_TAG" \
        --set image.pullPolicy=Never \
        --set config.dryRun=true \
        --set config.logLevel=INFO \
        --set config.enableJsonLogs=false \
        --set config.nodeMinAge=1s \
        --set config.deletionTimeout=5m \
        --set config.clusterName="helm-test-cluster" \
        --set 'config.unhealthyTaints[0]=node.kubernetes.io/not-ready' \
        --set 'config.unhealthyTaints[1]=node.kubernetes.io/unreachable' \
        --set 'config.protectionAnnotations.nodereaper\.io/do-not-delete=true' \
        --set 'config.protectionLabels.nodereaper\.io/protected=true' \
        --set 'config.removableFinalizers[0]=test.finalizer' \
        --set 'config.removableFinalizers[1]=safe.finalizer' \
        --set "config.nodeLabelSelector.cleanup-enabled=true" \
        --wait

    log_success "Helm chart installed"
}

# Run Helm tests
run_helm_tests() {
    log_info "Running Helm tests..."

    if helm test nodereaper -n nodereaper --timeout 300s; then
        log_success "Helm tests passed"
    else
        log_error "Helm tests failed"
        log_info "Checking test pod logs..."
        kubectl logs -n nodereaper -l "helm.sh/hook=test" --tail=100 || true
        return 1
    fi
}

# Main execution
main() {
    log_info "Starting Helm chart testing..."
    log_info "Using image: $IMAGE_REPO:$IMAGE_TAG"

    # Check cluster availability
    check_cluster

    # Build and load image
    build_and_load_image

    # Install Helm chart
    install_helm_chart

    # Verify deployment
    verify_deployment

    # Test with different selectors
    test_with_selector "cleanup-enabled=true"
    test_with_selector "instance-type=m5.large"
    test_with_selector "instance-type=m5.xlarge"

    # Show node information
    log_info "Cluster node information:"
    kubectl get nodes -o wide --show-labels | head -10

    # Run Helm tests
    run_helm_tests

    log_success "Helm chart testing completed successfully!"
    log_info "To clean up: scripts/cleanup.sh --helm-only"
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
