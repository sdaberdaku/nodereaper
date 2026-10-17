# Changelog

All notable changes to NodeReaper will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.1] - 2026-10-17

### Changed
- The chart's default `protectionAnnotations` include `karpenter.sh/do-not-disrupt=true`, the
  annotation Karpenter v1 uses. `karpenter.sh/do-not-evict=true` (Karpenter before v1) stays in
  the list.

## [1.3.0] - 2026-10-17

### Fixed
- Finalizer cleanup now removes finalizers. It sent a strategic merge patch, which merges
  `metadata.finalizers` with the existing list instead of replacing it, so nodes stuck in
  terminating state kept their finalizers and were reported again on every run. It now
  sends a JSON patch that replaces the list, guarded by a test on the node UID so a new node
  registered under the same name is never touched.
- A Kubernetes API error on one node no longer aborts the run: the node is skipped, and
  notifications for nodes already processed are always sent.
- No "cleanup" notification is sent when finalizer cleanup is disabled.

### Changed
- **Breaking**: nodes are deleted as unreachable or not ready only after their Ready condition
  has been `Unknown` or `False` for at least `deletionTimeout`. Before, a node was deleted on
  the first run after a kubelet restart or a short network blip.
- **Breaking**: invalid durations (for example `1h30m` or `500ms`) make NodeReaper fail at
  startup instead of silently becoming 10 minutes.
- **Breaking**: the chart's default `unhealthyTaints` is empty. The old default included
  `node.kubernetes.io/unschedulable`, which `kubectl cordon` adds, so cordoned nodes were
  deleted with their workloads.
- **Breaking**: the chart's default `removableFinalizers` is empty. Removing
  `karpenter.sh/termination` cuts Karpenter's drain short; use the NodePool's
  `terminationGracePeriod` to cap drain time instead.
- When Prometheus is enabled and the query fails, no nodes are deleted in that run. Before,
  NodeReaper fell back to checking only the current pods, which deletes nodes that are
  briefly empty between workloads.

### Added
- Integration test that runs the finalizer cleanup against a real API server.

## [1.2.1] - 2026-01-09

### Fixed
- Prometheus range selector: the lookback window is now an integer number of seconds
  (`[600s:]`), not a float (`[600.0s:]`), which Prometheus rejects.

## [1.2.0] - 2026-01-09

### Added
- Optional Prometheus integration (`prometheus.*` values). Nodes that had non-DaemonSet pods
  at any point during `minEmptyDuration` (default 10m) are not deleted, so a node that is
  briefly empty between workloads survives.
- Optional basic authentication for Prometheus, read from an existing secret.

### Changed
- The Slack webhook secret template is now `slack-secret.yaml`.

## [1.1.1] - 2025-12-27

### Changed
- Per-node log lines moved from INFO to DEBUG, with the analysis result logged per node.

## [1.1.0] - 2025-12-26

### Changed
- **Breaking**: `protectionAnnotations` and `protectionLabels` are lists of `key=value`
  strings instead of maps.

## [1.0.0] - 2025-12-26

### Added
- First public release: a Kubernetes CronJob (every 10 minutes by default) that deletes
  nodes running only DaemonSet pods, and nodes that are unreachable, not ready or carry a
  configured unhealthy taint.
- Minimum node age, protection annotations and labels, and a node label selector.
- Cleanup of allow-listed finalizers on nodes stuck in terminating state for longer than
  `deletionTimeout`.
- Dry-run mode, JSON logs and Slack notifications.
- Helm chart (OCI, `oci://ghcr.io/sdaberdaku/charts/nodereaper`) and multi-arch images
  (amd64, arm64) on GHCR.

[1.3.1]: https://github.com/sdaberdaku/nodereaper/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/sdaberdaku/nodereaper/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/sdaberdaku/nodereaper/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/sdaberdaku/nodereaper/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/sdaberdaku/nodereaper/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/sdaberdaku/nodereaper/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/sdaberdaku/nodereaper/releases/tag/v1.0.0
