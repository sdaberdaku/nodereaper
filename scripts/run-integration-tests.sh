#!/bin/bash

# Script to run NodeReaper integration tests
# Ensures proper test environment and runs comprehensive tests

set -e

CLUSTER_NAME="nodereaper-test"
SKIP_SETUP="${SKIP_SETUP:-false}"

echo "🧪 Running NodeReaper integration tests..."

# Function to check if cluster is available
check_cluster() {
    if kubectl cluster-info &> /dev/null; then
        echo "✅ Kubernetes cluster is available"
        return 0
    else
        echo "❌ Kubernetes cluster is not available"
        return 1
    fi
}

# Function to verify test cluster
verify_test_cluster() {
    echo "🔍 Verifying test cluster setup..."

    # Check node count
    node_count=$(kubectl get nodes --no-headers | wc -l)
    echo "   Nodes: $node_count"

    # Check for test labels
    test_nodes=$(kubectl get nodes -l test-environment=integration --no-headers | wc -l)
    if [[ $test_nodes -gt 0 ]]; then
        echo "   ✅ Found $test_nodes nodes with test labels"
    else
        echo "   ⚠️  No nodes with test labels found"
        echo "   This might not be a proper test cluster"
    fi

    # Show node labels for debugging
    echo "   Node labels:"
    kubectl get nodes --show-labels | head -5
}

# Function to run tests
run_tests() {
    echo "🏃 Running integration tests..."

    # Set test environment
    export PYTHONPATH="${PWD}/src:${PYTHONPATH:-}"

    # Run unittest-based integration tests
    echo "📝 Running unittest integration tests..."
    python -m pytest tests/integration/test_integration.py::TestNodeReaperIntegration -v

    # Run pytest-based integration tests
    echo "📝 Running pytest integration tests..."
    python -m pytest tests/integration/test_integration.py::TestNodeReaperIntegrationPytest -v -m integration

    echo "✅ All integration tests passed!"
}

# Function to run NodeReaper in test mode
run_nodereaper_test() {
    echo "🤖 Running NodeReaper in test mode..."

    # Set test environment variables
    export DRY_RUN=true
    export NODE_MIN_AGE=1s
    export LOG_LEVEL=DEBUG
    export NODE_LABEL_SELECTOR="cleanup-enabled=true"

    echo "   Running with label selector: $NODE_LABEL_SELECTOR"

    # Run NodeReaper
    python -c "
from src.nodereaper.reaper import NodeReaper
reaper = NodeReaper()
reaper.run()
"

    echo "✅ NodeReaper test run completed!"
}

# Main execution
main() {
    # Check if we should set up cluster
    if [[ "$SKIP_SETUP" != "true" ]]; then
        if ! check_cluster; then
            echo "🚀 Setting up test cluster..."
            ./scripts/setup-test-cluster.sh
        fi
    fi

    # Verify cluster
    if ! check_cluster; then
        echo "❌ Cannot connect to Kubernetes cluster"
        echo "💡 Try running: ./scripts/setup-test-cluster.sh"
        exit 1
    fi

    verify_test_cluster

    # Install dependencies if needed
    echo "📦 Installing test dependencies..."
    pip install -r requirements-dev.txt -q
    pip install -e . -q

    # Run tests
    run_tests

    # Run NodeReaper test
    run_nodereaper_test

    echo ""
    echo "🎉 Integration testing completed successfully!"
    echo ""
    echo "💡 Tips:"
    echo "   - View cluster: kubectl get nodes --show-labels"
    echo "   - Check pods: kubectl get pods --all-namespaces"
    echo "   - Clean up: kind delete cluster --name $CLUSTER_NAME"
}

# Handle command line arguments
case "${1:-}" in
    "--help"|"-h")
        echo "Usage: $0 [options]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --skip-setup   Skip cluster setup (use existing cluster)"
        echo ""
        echo "Environment variables:"
        echo "  SKIP_SETUP=true   Skip cluster setup"
        echo ""
        echo "Examples:"
        echo "  $0                        # Set up kind cluster and run tests"
        echo "  SKIP_SETUP=true $0        # Use existing cluster"
        exit 0
        ;;
    "--skip-setup")
        SKIP_SETUP=true
        shift
        ;;
esac

# Run main function
main "$@"
