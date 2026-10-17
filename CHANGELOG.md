# Changelog

All notable changes to NodeReaper will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.2] - 2026-10-17

### Fixed
- Finalizer cleanup now removes finalizers. It sent a strategic merge patch, which merges
  `metadata.finalizers` with the existing list instead of replacing it, so nodes stuck in
  terminating state kept their finalizers and were reported again on every run. It now
  sends a JSON patch that replaces the list.

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

[1.2.2]: https://github.com/sdaberdaku/nodereaper/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/sdaberdaku/nodereaper/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/sdaberdaku/nodereaper/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/sdaberdaku/nodereaper/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/sdaberdaku/nodereaper/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/sdaberdaku/nodereaper/releases/tag/v1.0.0
