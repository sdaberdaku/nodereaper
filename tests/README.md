# NodeReaper Testing Guide

This document describes the comprehensive testing strategy for NodeReaper, including unit tests, integration tests, and Helm tests.

## Test Structure

```
tests/
├── README.md                    # This file
├── __init__.py                  # Test package initialization
├── integration/                 # Integration tests
│   ├── __init__.py
│   └── test_integration.py      # End-to-end tests with real K8s
├── test_*.py                    # Unit tests
└── conftest.py                  # Pytest configuration (if needed)
```

## Test Types

### 1. Unit Tests (97% Coverage)

**Location**: `tests/test_*.py`
**Command**: `make test` or `pytest tests/ -m "not integration"`

Comprehensive unit tests covering all modules:

- **`test_settings.py`** - Configuration parsing and environment variables
- **`test_notification.py`** - Notification system with auto-registration
- **`test_logging.py`** - JSON and text logging functionality
- **`test_k8s_exception.py`** - Kubernetes exception handling
- **`test_node_analyzer.py`** - Node analysis and decision logic
- **`test_k8s_client.py`** - Kubernetes API client operations
- **`test_reaper.py`** - Main NodeReaper orchestration

**Features**:
- Mock all external dependencies
- Test error conditions and edge cases
- Verify configuration loading
- Test notification system with decorators
- Comprehensive finalizer logic testing

### 2. Integration Tests

**Location**: `tests/integration/test_integration.py`
**Command**: `make test-integration` or `scripts/run-integration-tests.sh`

Real Kubernetes cluster tests:

#### Test Classes:

**`TestKubernetesIntegration`**:
- Kubernetes client connectivity
- Node and pod listing with selectors
- Node analyzer with real cluster data
- Dry-run mode verification
- Pod creation and management
- Permission validation

**`TestNodeReaperEndToEnd`**:
- Complete NodeReaper workflow
- Configuration loading from environment
- End-to-end dry-run execution

#### Requirements:
- Kind cluster with test labels
- Proper RBAC permissions
- Test namespace creation
- Safe dry-run mode only

### 3. Helm Tests

**Location**: `helm/templates/tests/`
**Command**: `make test-helm` or `helm test nodereaper`

#### Test Files:

**`test-cronjob.yaml`** - Deployment validation:
- CronJob existence and configuration
- ServiceAccount and RBAC setup
- Environment variable validation
- Security context verification
- Resource limits checking
- Slack configuration (if enabled)
- Finalizer cleanup settings
- Logging configuration

**`test-functionality.yaml`** - Functional testing:
- Runs integration tests inside cluster
- Uses NodeReaper image with pytest
- Validates real functionality
- Safe dry-run mode only

## Running Tests

### Prerequisites

```bash
# Install development dependencies
make install-dev

# For integration tests, install additional tools
# - kind (Kubernetes in Docker)
# - kubectl
# - helm
# - docker
```

### Unit Tests

```bash
# Run all unit tests
make test

# Run with coverage
make test-cov

# Run specific test file
pytest tests/test_settings.py -v

# Run specific test
pytest tests/test_settings.py::TestDurationParsing::test_parse_duration_seconds -v
```

### Integration Tests

```bash
# Run with existing cluster
make test-integration

# Create cluster and run tests
make test-integration-create

# Manual cluster setup and test
scripts/run-integration-tests.sh --create-cluster --cleanup

# Run only integration tests (skip Helm tests)
scripts/run-integration-tests.sh --skip-helm-tests
```

### Helm Tests

```bash
# Test Helm chart deployment
make test-helm

# Manual Helm testing
scripts/test-helm-chart.sh

# Test with specific cluster
scripts/test-helm-chart.sh my-cluster-name
```

### All Tests

```bash
# Run everything (unit + integration + helm)
make test-all
```

## Test Configuration

### Environment Variables

Integration and Helm tests use these environment variables:

```bash
# Core settings
DRY_RUN=true                    # Always true for safety
LOG_LEVEL=DEBUG                 # Verbose logging for tests
ENABLE_JSON_LOGS=false          # Text logs for readability

# Test-specific settings
NODE_MIN_AGE=1s                 # Short age for testing
DELETION_TIMEOUT=5m             # Reasonable timeout
CLUSTER_NAME=test-cluster       # Test cluster identifier

# Safety configurations
UNHEALTHY_TAINTS=node.kubernetes.io/not-ready,node.kubernetes.io/unreachable
PROTECTION_ANNOTATIONS=nodereaper.io/do-not-delete=true
PROTECTION_LABELS=nodereaper.io/protected=true
REMOVABLE_FINALIZERS=test.finalizer,safe.finalizer
```

### Kind Cluster Configuration

The integration tests create a kind cluster with:

- 1 control-plane node
- 3 worker nodes with different labels
- Test environment labels
- Various instance types and zones
- Protection labels on some nodes

## Test Safety

### Safety Measures

1. **Dry-run Mode**: All tests run in dry-run mode - no actual node deletions
2. **Test Clusters**: Only run on clusters with test labels or kind clusters
3. **Context Validation**: Verify correct cluster context before running
4. **Namespace Isolation**: Use dedicated test namespaces
5. **Resource Cleanup**: Automatic cleanup after tests

### Cluster Requirements

Integration tests will only run on clusters that meet these criteria:

- Cluster name contains "kind", "minikube", or "test"
- OR nodes have `test-environment: integration` label
- Current kubectl context matches expected pattern

## Troubleshooting

### Common Issues

**"Kubernetes cluster not available"**:
```bash
# Check cluster status
kubectl cluster-info

# Create test cluster
make test-integration-create
```

**"Wrong cluster context"**:
```bash
# List contexts
kubectl config get-contexts

# Switch context
kubectl config use-context kind-nodereaper-test
```

**"Helm tests failed"**:
```bash
# Check test pod logs
kubectl logs -n nodereaper -l "helm.sh/hook=test" --tail=100

# Check CronJob status
kubectl get cronjob nodereaper -n nodereaper -o yaml
```

**"Integration tests skipped"**:
- Ensure cluster has proper test labels
- Verify RBAC permissions
- Check cluster connectivity

### Debug Commands

```bash
# Check cluster nodes and labels
kubectl get nodes --show-labels

# Verify NodeReaper deployment
kubectl get all -n nodereaper

# Check RBAC permissions
kubectl auth can-i list nodes
kubectl auth can-i patch nodes
kubectl auth can-i list pods

# View NodeReaper logs
kubectl logs -n nodereaper -l app.kubernetes.io/name=nodereaper --tail=50
```

## Continuous Integration

The CI pipeline runs:

1. **Unit Tests**: Fast feedback on code changes
2. **Integration Tests**: Full end-to-end validation
3. **Helm Tests**: Deployment and configuration validation
4. **Coverage Reports**: Ensure comprehensive testing

### CI Configuration

See `.github/workflows/ci.yml` for the complete CI setup including:
- Multi-platform testing
- Kind cluster setup
- Docker image building
- Test result reporting
- Coverage analysis

## Contributing

When adding new features:

1. **Write unit tests first** - Aim for >95% coverage
2. **Add integration tests** - For end-to-end scenarios
3. **Update Helm tests** - If configuration changes
4. **Test locally** - Run `make test-all` before submitting
5. **Update documentation** - Keep this guide current

### Test Guidelines

- Use descriptive test names
- Test both success and failure cases
- Mock external dependencies in unit tests
- Use real resources in integration tests (safely)
- Clean up test resources
- Add comments for complex test scenarios
