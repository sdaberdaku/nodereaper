#!/bin/bash

# Integration test runner for NodeReaper
# This script sets up a kind cluster and runs integration tests

set -euo pipefail

# Configuration
CLUSTER_NAME="${CLUSTER_NAME:-nodereaper-test}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
KIND_CONFIG_FILE="$PROJECT_ROOT/.kiro/kind-config.yaml"

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

# Check if required tools are installed
check_dependencies() {
    log_info "Checking dependencies..."

    local missing_deps=()

    if ! command -v kind &> /dev/null; then
        missing_deps+=("kind")
    fi

    if ! command -v kubectl &> /dev/null; then
        missing_deps+=("kubectl")
    fi

    if ! command -v docker &> /dev/null; then
        missing_deps+=("docker")
    fi

    if ! command -v helm &> /dev/null; then
        missing_deps+=("helm")
    fi

    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "Missing required dependencies: ${missing_deps[*]}"
        log_info "Please install the missing tools and try again"
        exit 1
    fi

    log_success "All dependencies found"
}

# Check if cluster is available and has the expected name
check_cluster() {
    log_info "Checking cluster availability..."

    if ! kubectl cluster-info &> /dev/null; then
        log_error "No Kubernetes cluster available"
        return 1
    fi

    # Check if we're using the expected context
    local current_context
    current_context=$(kubectl config current-context)
    local expected_context="kind-${CLUSTER_NAME}"

    if [ "$current_context" != "$expected_context" ]; then
        log_error "Current context '$current_context' does not match expected '$expected_context'"
        log_info "Please ensure you're using the correct cluster context"
        return 1
    fi

    log_success "Cluster is available and context is correct"
    return 0
}

# Create kind cluster configuration
create_kind_config() {
    log_info "Creating kind cluster configuration..."

    mkdir -p "$(dirname "$KIND_CONFIG_FILE")"

    cat > "$KIND_CONFIG_FILE" << EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: ${CLUSTER_NAME}
nodes:
- role: control-plane
  labels:
    test-environment: integration
- role: worker
  labels:
    cleanup-enabled: "true"
    instance-type: m5.large
    zone: us-west-2a
    test-environment: integration
- role: worker
  labels:
    cleanup-enabled: "true"
    instance-type: m5.large
    zone: us-west-2b
    test-environment: integration
- role: worker
  labels:
    cleanup-enabled: "false"
    instance-type: m5.xlarge
    zone: us-west-2c
    test-environment: integration
    nodereaper.io/protected: "true"
EOF

    log_success "Kind configuration created at $KIND_CONFIG_FILE"
}

# Create kind cluster
create_cluster() {
    log_info "Creating kind cluster '$CLUSTER_NAME'..."

    if kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
        log_warning "Cluster '$CLUSTER_NAME' already exists"
        return 0
    fi

    create_kind_config

    if ! kind create cluster --config "$KIND_CONFIG_FILE"; then
        log_error "Failed to create kind cluster"
        return 1
    fi

    # Wait for cluster to be ready
    log_info "Waiting for cluster to be ready..."
    kubectl wait --for=condition=Ready nodes --all --timeout=300s

    log_success "Kind cluster '$CLUSTER_NAME' created successfully"
}

# Install NodeReaper using Helm
install_nodereaper() {
    log_info "Installing NodeReaper with Helm..."

    # Create namespace
    kubectl create namespace nodereaper --dry-run=client -o yaml | kubectl apply -f -

    # Install with test configuration
    helm upgrade --install nodereaper "$PROJECT_ROOT/helm" \
        --namespace nodereaper \
        --set config.dryRun=true \
        --set config.logLevel=DEBUG \
        --set config.enableJsonLogs=false \
        --set config.nodeMinAge=1s \
        --set config.deletionTimeout=5m \
        --set config.clusterName="integration-test-cluster" \
        --set 'config.unhealthyTaints[0]=node.kubernetes.io/not-ready' \
        --set 'config.unhealthyTaints[1]=node.kubernetes.io/unreachable' \
        --set 'config.protectionAnnotations.nodereaper\.io/do-not-delete=true' \
        --set 'config.protectionLabels.nodereaper\.io/protected=true' \
        --set 'config.removableFinalizers[0]=test.finalizer' \
        --set 'config.removableFinalizers[1]=safe.finalizer' \
        --wait

    log_success "NodeReaper installed successfully"
}

# Run integration tests
run_integration_tests() {
    log_info "Running integration tests..."

    cd "$PROJECT_ROOT"

    # Set environment variables for tests
    export DRY_RUN=true
    export LOG_LEVEL=DEBUG
    export ENABLE_JSON_LOGS=false
    export NODE_MIN_AGE=1s
    export DELETION_TIMEOUT=5m
    export CLUSTER_NAME=integration-test-cluster
    export UNHEALTHY_TAINTS="node.kubernetes.io/not-ready,node.kubernetes.io/unreachable"
    export PROTECTION_ANNOTATIONS="nodereaper.io/do-not-delete=true"
    export PROTECTION_LABELS="nodereaper.io/protected=true"
    export REMOVABLE_FINALIZERS="test.finalizer,safe.finalizer"

    # Run integration tests
    if python -m pytest tests/integration/ -v --tb=short -m integration; then
        log_success "Integration tests passed"
    else
        log_error "Integration tests failed"
        return 1
    fi
}

# Run Helm tests
run_helm_tests() {
    log_info "Running Helm tests..."

    if helm test nodereaper --namespace nodereaper --timeout 300s; then
        log_success "Helm tests passed"
    else
        log_error "Helm tests failed"
        log_info "Checking test pod logs..."
        kubectl logs -n nodereaper -l "helm.sh/hook=test" --tail=50 || true
        return 1
    fi
}

# Clean up resources
cleanup() {
    log_info "Cleaning up resources..."

    # Uninstall Helm release
    if helm list -n nodereaper | grep -q nodereaper; then
        helm uninstall nodereaper -n nodereaper || true
    fi

    # Delete namespace
    kubectl delete namespace nodereaper --ignore-not-found=true || true

    # Delete kind cluster if requested
    if [ "${DELETE_CLUSTER:-false}" = "true" ]; then
        if kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
            log_info "Deleting kind cluster '$CLUSTER_NAME'..."
            kind delete cluster --name "$CLUSTER_NAME"
            log_success "Kind cluster deleted"
        fi
    fi

    # Clean up kind config
    if [ -f "$KIND_CONFIG_FILE" ]; then
        rm -f "$KIND_CONFIG_FILE"
    fi
}

# Main execution
main() {
    log_info "Starting NodeReaper integration tests..."

    # Parse command line arguments
    local create_cluster_flag=false
    local run_tests_flag=true
    local run_helm_tests_flag=true
    local cleanup_flag=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --create-cluster)
                create_cluster_flag=true
                shift
                ;;
            --skip-tests)
                run_tests_flag=false
                shift
                ;;
            --skip-helm-tests)
                run_helm_tests_flag=false
                shift
                ;;
            --cleanup)
                cleanup_flag=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --create-cluster     Create a new kind cluster"
                echo "  --skip-tests         Skip integration tests"
                echo "  --skip-helm-tests    Skip Helm tests"
                echo "  --cleanup            Clean up resources after tests"
                echo "  --help               Show this help message"
                echo ""
                echo "Environment variables:"
                echo "  CLUSTER_NAME         Name of the kind cluster (default: nodereaper-test)"
                echo "  DELETE_CLUSTER       Delete cluster after cleanup (default: false)"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    # Set up trap for cleanup on exit
    if [ "$cleanup_flag" = "true" ]; then
        trap cleanup EXIT
    fi

    # Check dependencies
    check_dependencies

    # Create cluster if requested
    if [ "$create_cluster_flag" = "true" ]; then
        create_cluster
    fi

    # Check cluster availability
    if ! check_cluster; then
        log_error "Cluster check failed. Use --create-cluster to create a new cluster."
        exit 1
    fi

    # Install NodeReaper
    install_nodereaper

    # Run integration tests
    if [ "$run_tests_flag" = "true" ]; then
        run_integration_tests
    fi

    # Run Helm tests
    if [ "$run_helm_tests_flag" = "true" ]; then
        run_helm_tests
    fi

    log_success "All tests completed successfully!"
}

# Run main function with all arguments
main "$@"
