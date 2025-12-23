# NodeReaper

[![CI](https://github.com/sdaberdaku/nodereaper/workflows/CI/badge.svg)](https://github.com/sdaberdaku/nodereaper/actions/workflows/ci.yml)
[![Release](https://github.com/sdaberdaku/nodereaper/workflows/Release/badge.svg)](https://github.com/sdaberdaku/nodereaper/actions/workflows/release.yml)
[![Version](https://img.shields.io/github/v/release/sdaberdaku/nodereaper)](https://github.com/sdaberdaku/nodereaper/releases)
[![Docker Image](https://img.shields.io/badge/Docker-GHCR-blue)](https://github.com/sdaberdaku/nodereaper/pkgs/container/nodereaper)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**A cost-saving failsafe for Kubernetes clusters that automatically cleans up empty nodes when autoscalers fail.**

Sometimes autoscalers (Cluster Autoscaler, Karpenter, etc.) fail to scale down expensive nodes, leaving them running with only system pods. NodeReaper acts as a **reliable failsafe** that detects and removes these "zombie" nodes.

## Features

- **Empty node detection** - Identifies nodes with only DaemonSet pods
- **Cost-saving failsafe** - Catches nodes that autoscalers missed
- **Age-based policy** - Avoids deleting newly provisioned nodes
- **Autoscaler integration** - Respects deletion markers from any autoscaler
- **Unreachable node handling** - Cleans up nodes in Unknown state
- **Protection system** - Multiple layers of protection via annotations and labels
- **Finalizer cleanup** - Intelligent cleanup of stuck finalizers
- **Slack notifications** - Get notified when nodes are deleted
- **Dry-run mode** - Test safely before enabling deletions

## Quick Start

```bash
# Install with Helm
helm install nodereaper oci://ghcr.io/sdaberdaku/charts/nodereaper \
  --namespace nodereaper \
  --create-namespace
```

## Configuration

### Key Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `config.nodeMinAge` | Minimum node age before deletion | `10m` |
| `config.deletionTimeout` | Timeout before taking over marked nodes | `15m` |
| `config.deletionTaints` | List of exact taint keys indicating deletion | See below |
| `config.protectionAnnotations` | Map of annotation key-value pairs providing protection | See below |
| `config.protectionLabels` | Map of label key-value pairs providing protection | See below |
| `config.enableFinalizerCleanup` | Enable finalizer cleanup for stuck nodes | `true` |
| `config.finalizerTimeout` | Timeout before removing stuck finalizers | `5m` |
| `config.finalizerWhitelist` | List of exact finalizer names safe to remove | See below |
| `config.finalizerBlacklist` | List of exact finalizer names never to remove | `[]` |
| `config.dryRun` | Enable dry-run mode (no actual deletions) | `false` |
| `config.nodeLabelSelector` | Map of key-value pairs to filter nodes | `{}` |

### Protection System

NodeReaper uses the following protection and deletion markers:

```yaml
config:
  # Taint keys that indicate deletion
  deletionTaints:
    - "karpenter.sh/disrupted"
    - "node.kubernetes.io/unreachable"
    - "node.kubernetes.io/unschedulable"

  # Annotation key-value pairs that provide protection
  protectionAnnotations:
    "karpenter.sh/do-not-evict": "true"
    "cluster-autoscaler.kubernetes.io/scale-down-disabled": "true"
    "nodereaper.io/do-not-delete": "true"

  # Label key-value pairs that provide protection
  protectionLabels:
    "karpenter.sh/do-not-evict": "true"
    "cluster-autoscaler.kubernetes.io/scale-down-disabled": "true"
    "nodereaper.io/do-not-delete": "true"
```

### Finalizer Management

```yaml
config:
  # Enable intelligent finalizer cleanup
  enableFinalizerCleanup: true

  # How long to wait before cleaning up stuck finalizers
  finalizerTimeout: "5m"

  # Exact finalizer names safe to remove (whitelist approach)
  finalizerWhitelist:
    - "karpenter.sh/termination"
    - "node.kubernetes.io/exclude-from-external-load-balancers"

  # Exact finalizer names never to remove (blacklist approach)
  finalizerBlacklist: []
```

**How it works:**
- Nodes with **protection annotations or labels** are never deleted
- Nodes with **deletion taints** are protected for `deletionTimeout` duration
- After timeout expires, NodeReaper takes over if the node meets deletion criteria
- Stuck finalizers are cleaned up based on whitelist/blacklist configuration

### Advanced Configuration

#### CronJob Settings
```yaml
cronjob:
  schedule: "*/10 * * * *"              # Run every 10 minutes
  successfulJobsHistoryLimit: 3         # Keep 3 successful job logs
  failedJobsHistoryLimit: 1             # Keep 1 failed job log
  startingDeadlineSeconds: 300          # Job start deadline
  concurrencyPolicy: Forbid             # Don't run concurrent jobs
```

#### Slack Notifications
```yaml
slack:
  enabled: true
  webhookUrl: "https://hooks.slack.com/services/YOUR/WEBHOOK"

  # Or use existing secret
  existingSecret:
    name: "slack-webhook"
    key: "webhook-url"
```

#### Node Filtering
```yaml
config:
  # Only consider nodes with these labels for deletion
  nodeLabelSelector:
    cleanup-enabled: "true"
    instance-type: "m5.large"
    zone: "us-west-2a"

  # Set cluster name for notifications
  clusterName: "production-cluster"
```

## How It Works

🔍 **Discovery**: Scans all nodes in the cluster (or filtered by labels)
⏳ **Safety Check**: Skips nodes that are too young or protected by annotations/labels
🎯 **Smart Detection**: Identifies truly empty nodes (only DaemonSet pods running)
⚖️ **Autoscaler Respect**: Honors deletion markers from any autoscaler for configured timeout
🗑️ **Clean Removal**: Safely deletes empty nodes that autoscalers missed
🔧 **Finalizer Cleanup**: Removes stuck finalizers from terminating nodes
📢 **Notification**: Alerts you via Slack when nodes are cleaned up

### Deletion Reasons

NodeReaper provides clear reasons for each deletion:

- **`empty`** - Node only has DaemonSet pods running
- **`unreachable`** - Node is in Unknown state (likely failed)
- **`unschedulable`** - Node is cordoned (has unschedulable taint)
- **`takeover-empty`** - Taking over deletion of empty node from autoscaler (after timeout)
- **`takeover-unreachable`** - Taking over deletion of unreachable node from autoscaler
- **`takeover-unschedulable`** - Taking over deletion of unschedulable node from autoscaler

## Development

```bash
# Setup
git clone https://github.com/sdaberdaku/nodereaper.git
cd nodereaper
make install-dev

# Testing
make test              # Unit tests
make test-integration  # Integration tests with kind
make test-all          # All tests
make checks            # Quality checks

# Local testing
make setup-cluster     # Set up kind cluster
DRY_RUN=true LOG_LEVEL=DEBUG nodereaper
```

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.
