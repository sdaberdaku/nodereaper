# NodeReaper

<div align="center">
  <img src="nodereaper_logo.jpeg" alt="NodeReaper Logo" width="400"/>

  *Automatically harvests empty and unhealthy nodes when autoscalers fail to scale down*
</div>

<div align="center">

[![CI](https://github.com/sdaberdaku/nodereaper/workflows/CI/badge.svg)](https://github.com/sdaberdaku/nodereaper/actions/workflows/ci.yml)
[![Release](https://github.com/sdaberdaku/nodereaper/workflows/Release/badge.svg)](https://github.com/sdaberdaku/nodereaper/actions/workflows/release.yml)
[![Version](https://img.shields.io/github/v/release/sdaberdaku/nodereaper)](https://github.com/sdaberdaku/nodereaper/releases)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

</div>

---

NodeReaper acts as a cost-saving failsafe that detects and removes nodes running only system pods, helping reduce cloud costs when autoscalers miss cleanup opportunities. Like the Grim Reaper, it comes for nodes whose time has come - but only the ones that truly deserve it.

Sometimes autoscalers (Cluster Autoscaler, Karpenter, etc.) fail to scale down expensive nodes, leaving them running with only system pods. NodeReaper acts as a **reliable failsafe** that detects and removes these "zombie" nodes.

## What It Does

1. **Scans nodes** every 10 minutes (configurable)
2. **Skips protected nodes** with protection annotations or labels
3. **Waits for minimum age** before considering nodes for deletion
4. **Identifies empty nodes** that only run DaemonSet pods
5. **Removes unhealthy nodes** that are unreachable or not ready
6. **Cleans stuck finalizers** from nodes that won't terminate
7. **Sends notifications** when nodes are deleted


## Quick Start

```bash
# Install with Helm
helm install nodereaper oci://ghcr.io/sdaberdaku/charts/nodereaper \
  --namespace nodereaper \
  --create-namespace
```

## Safety Features

- **Dry-run mode** - Test without actually deleting nodes
- **Age protection** - Never deletes newly created nodes
- **Annotation protection** - Respects "do not delete" markers
- **Label protection** - Skips nodes with protection labels
- **Finalizer whitelist** - Only removes known-safe finalizers

## Development

```yaml
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
