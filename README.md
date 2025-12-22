# NodeReaper

[![CI](https://github.com/sdaberdaku/nodereaper/workflows/CI/badge.svg)](https://github.com/sdaberdaku/nodereaper/actions/workflows/ci.yml)
[![Release](https://github.com/sdaberdaku/nodereaper/workflows/Release/badge.svg)](https://github.com/sdaberdaku/nodereaper/actions/workflows/release.yml)
[![Version](https://img.shields.io/github/v/release/sdaberdaku/nodereaper)](https://github.com/sdaberdaku/nodereaper/releases)
[![Docker Image](https://img.shields.io/badge/Docker-GHCR-blue)](https://github.com/sdaberdaku/nodereaper/pkgs/container/nodereaper)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Helm Chart](https://img.shields.io/badge/Helm-Chart-blue)](https://github.com/sdaberdaku/nodereaper/releases)

**A cost-saving failsafe for Kubernetes clusters that automatically cleans up empty nodes when autoscalers fail.**

Sometimes Kubernetes autoscalers (Cluster Autoscaler, Karpenter, etc.) fail to scale down expensive nodes, leaving them running with only system pods. This can result in significant unnecessary cloud costs, especially with large instance types that should have been terminated hours or days ago.

NodeReaper acts as a **reliable failsafe** that detects and removes these "zombie" nodes, ensuring your cluster doesn't accumulate costly empty nodes when autoscaling doesn't work as expected.

## Why NodeReaper?

**💰 Cost Optimization**: Prevent expensive nodes from running indefinitely when autoscalers fail
**🛡️ Failsafe Protection**: Works alongside (not instead of) your existing autoscaler
**🎯 Smart Detection**: Only removes truly empty nodes (with just DaemonSet pods)
**⚡ Battle-tested**: Production-ready with comprehensive safety checks

## Features

- **Empty node detection** - Identifies nodes with only DaemonSet pods
- **Cost-saving failsafe** - Catches nodes that autoscalers missed
- **Age-based policy** - Avoids deleting newly provisioned nodes
- **Karpenter integration** - Respects Karpenter deletion markers
- **Unreachable node handling** - Cleans up nodes in Unknown state
- **Label filtering** - Target specific nodes using label selectors
- **Slack notifications** - Get notified when nodes are deleted
- **Dry-run mode** - Test safely before enabling deletions
- **Multi-arch support** - AMD64 and ARM64 Docker images

## Common Scenarios

NodeReaper helps in these real-world situations:

**🔥 Autoscaler Bugs**: Cluster Autoscaler or Karpenter fails to scale down due to bugs, misconfigurations, or edge cases
**⏰ Timing Issues**: Nodes become empty after the autoscaler's evaluation window
**🚫 Blocked Scale-down**: PodDisruptionBudgets or other policies prevent normal autoscaling
**💥 Workload Crashes**: Applications crash leaving nodes empty, but autoscaler doesn't react quickly
**🔧 Maintenance Windows**: Nodes emptied during maintenance but not cleaned up afterward
**💸 Cost Alerts**: You notice high cloud bills from nodes that should have been terminated

**Real Example**: A `c5.24xlarge` instance ($3.456/hour) gets stuck empty for a weekend due to an autoscaler bug. NodeReaper would have saved you **$166** by cleaning it up automatically.

## Installation

### Helm (Recommended)

```bash
# Install from OCI registry (recommended)
helm install nodereaper oci://ghcr.io/sdaberdaku/charts/nodereaper \
  --namespace nodereaper \
  --create-namespace

# Or install from GitHub releases
helm install nodereaper https://github.com/sdaberdaku/nodereaper/releases/latest/download/nodereaper-1.0.0.tgz \
  --namespace nodereaper \
  --create-namespace
```

### Production Setup

```bash
helm install nodereaper oci://ghcr.io/sdaberdaku/charts/nodereaper \
  --namespace nodereaper \
  --create-namespace \
  --set config.dryRun=false \
  --set config.nodeMinAge=15m \
  --set config.nodeLabelSelector="cleanup-enabled=true" \
  --set slack.enabled=true \
  --set slack.webhookUrl="https://hooks.slack.com/services/YOUR/WEBHOOK"
```

## Configuration

### Key Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `config.nodeMinAge` | Minimum node age before deletion | `10m` |
| `config.dryRun` | Enable dry-run mode (no actual deletions) | `false` |
| `config.clusterName` | Cluster name for notifications (shows "unknown" if not set) | `""` |
| `config.nodeLabelSelector` | Label selector to filter nodes | `""` |
| `cronjob.schedule` | Cron schedule for execution | `*/10 * * * *` |
| `slack.enabled` | Enable Slack notifications | `false` |
| `slack.webhookUrl` | Slack webhook URL | `""` |

### Cluster Name Configuration

Set the cluster name for notifications and logging:
```bash
--set config.clusterName="my-production-cluster"
```

If not set, notifications will show "unknown" as the cluster name.

### RBAC Permissions

NodeReaper requires these minimal cluster-level permissions:
- **nodes**: `get`, `list`, `delete` - Core functionality
- **pods**: `get`, `list` - Check what's running on nodes

The Helm chart automatically creates the required RBAC resources.

### Node Label Filtering

Target specific nodes using label selectors:

```bash
# Only nodes with cleanup enabled
--set config.nodeLabelSelector="cleanup-enabled=true"

# Specific instance type
--set config.nodeLabelSelector="instance-type=m5.large"

# Multiple labels (AND logic)
--set config.nodeLabelSelector="zone=us-west-2a,cleanup-enabled=true"
```

## How It Works

NodeReaper runs as a **failsafe** alongside your existing autoscaler:

🔍 **Discovery**: Scans all nodes in the cluster (or filtered by labels)
⏳ **Safety Check**: Skips nodes that are too young or marked by Karpenter
🎯 **Smart Detection**: Identifies truly empty nodes (only DaemonSet pods running)
🗑️ **Clean Removal**: Safely deletes empty nodes that autoscalers missed
📢 **Notification**: Alerts you via Slack when nodes are cleaned up

**Safety First**: NodeReaper is designed to be conservative - it will never delete nodes with actual workloads, only those that should have been cleaned up already.

### Detailed Process

1. **Lists nodes** in the cluster (filtered by labels if configured)
2. **Skips nodes** that are:
   - Younger than `nodeMinAge` (default: 10 minutes)
   - Already marked for deletion by Karpenter
   - Have non-DaemonSet workloads running
3. **Deletes nodes** that are:
   - Unreachable (Ready status = Unknown)
   - Empty (only running DaemonSet pods like kube-proxy, CNI, monitoring agents)

## Development

### Setup

```bash
git clone https://github.com/sdaberdaku/nodereaper.git
cd nodereaper
make install-dev
```

### Testing

```bash
# Run unit tests
make test

# Run integration tests with kind
make test-integration

# Run Helm chart tests (includes helm test)
make test-helm

# Run all tests
make test-all

# Run quality checks (lint + test + helm checks)
make checks
```

### Development

```bash
# Set up development environment
make dev-setup

# See all available commands
make help

# Format code
make format

# Set up test cluster
make setup-cluster

# Clean up everything
make cleanup
```

### Manual Testing

```bash
# Set up test cluster
make setup-test-cluster

# Test NodeReaper in dry-run mode
DRY_RUN=true LOG_LEVEL=DEBUG nodereaper

# Clean up everything
scripts/cleanup.sh

# Clean up only Helm release
scripts/cleanup.sh --helm-only

# Clean up only kind cluster
scripts/cleanup.sh --cluster-only
```

## Docker Images

Multi-architecture images are available at:
```
ghcr.io/sdaberdaku/nodereaper:latest
ghcr.io/sdaberdaku/nodereaper:v1.0.0
```

Supported platforms: `linux/amd64`, `linux/arm64`

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Run `make all-checks` before committing
4. Submit a pull request
