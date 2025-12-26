# Changelog

All notable changes to NodeReaper will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2025-12-23

### Changed
- **Code Modernization**: Updated to modern Python 3.9+ type hints
  - Replaced `typing.Dict`, `typing.List`, `typing.Optional` with built-in `dict`, `list`, `| None`
  - Updated all type annotations across the codebase for better readability
- **Improved Code Structure**: Simplified import system
  - Removed `src` prefix from imports for cleaner developer experience
  - Updated package configuration for professional import names (`from nodereaper.config` instead of `from src.nodereaper.config`)
- **Enhanced Code Quality**: Modernized conditional logic
  - Converted duration parsing to use `match/case` syntax for better readability
  - Simplified finalizer configuration by removing blacklist complexity
  - Consolidated redundant methods in KubernetesClient class

### Improved
- **Configuration Management**: Moved all string processing to config module for better separation of concerns
- **Error Handling**: Removed redundant config validation checks and improved failsafe handling
- **Method Consolidation**: Unified finalizer cleanup methods into single `_cleanup_stuck_finalizers` method
- **Type Safety**: Added comprehensive type annotations to all KubernetesClient methods
- **Import Consistency**: Standardized to use `k8s` and `k8s_config` aliases for kubernetes imports

### Developer Experience
- Cleaner import structure improves code maintainability
- Better type hints provide enhanced IDE support and code completion
- Simplified configuration reduces complexity for contributors
- Modern Python syntax improves code readability

## [1.2.0] - 2025-12-23

### Changed
- **BREAKING**: `nodeLabelSelector` configuration format changed from list to map
  - **Before**: `nodeLabelSelector: ["cleanup-enabled=true", "instance-type=m5.large"]`
  - **After**: `nodeLabelSelector: {cleanup-enabled: "true", instance-type: "m5.large"}`
- All matching operations now use exact matching instead of pattern matching:
  - `finalizerWhitelist` and `finalizerBlacklist` use exact finalizer names
  - `deletionTaints` use exact taint keys
  - `protectionAnnotations` and `protectionLabels` use exact key-value pairs
- Updated default `deletionTaints` to include only essential taint keys:
  - `karpenter.sh/disrupted`
  - `node.kubernetes.io/unreachable`
  - `node.kubernetes.io/unschedulable`

### Added
- Protection labels functionality with exact key-value matching
- Enhanced cluster verification in test scripts to check actual cluster name
- Comprehensive test coverage for new configuration formats
- Better error handling and validation for configuration parsing

### Fixed
- Helm template coalesce warnings when using map-based configurations
- Test scripts updated to use new map format for `nodeLabelSelector`
- Improved template logic for handling different value types (strings, numbers, booleans)

### Documentation
- Updated README with new configuration format examples
- Added comprehensive configuration reference for all exact matching features
- Updated Helm chart documentation to reflect new map-based configurations
- Added troubleshooting section for common configuration issues

## [1.1.0] - 2025-12-22

### Added
- Force delete functionality with intelligent finalizer cleanup
- Configurable finalizer whitelist and blacklist for safe cleanup
- Protection annotations and labels for permanent node protection
- Autoscaler-agnostic deletion markers with configurable patterns
- Enhanced logging with detailed deletion reasons
- Comprehensive test coverage including integration tests

### Changed
- Removed Karpenter-specific health checking logic
- Made tool completely autoscaler-agnostic
- Improved configuration validation and error handling

### Fixed
- Finalizer cleanup timeout handling
- Node age calculation accuracy
- Memory and resource usage optimization

## [1.0.0] - 2025-12-21

### Added
- Initial release of NodeReaper
- Empty node detection (nodes with only DaemonSet pods)
- Unschedulable node detection and cleanup
- Age-based deletion policy
- Slack notifications support
- Dry-run mode for safe testing
- Helm chart for easy deployment
- Multi-architecture Docker images (amd64, arm64)
- Comprehensive CI/CD pipeline
- RBAC configuration with minimal required permissions

### Features
- Kubernetes cluster integration with in-cluster and external config support
- Configurable node minimum age before deletion
- Integration with cluster autoscalers (Karpenter, Cluster Autoscaler)
- Detailed logging and monitoring capabilities
- Production-ready security configurations

[1.3.0]: https://github.com/sdaberdaku/nodereaper/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/sdaberdaku/nodereaper/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/sdaberdaku/nodereaper/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/sdaberdaku/nodereaper/releases/tag/v1.0.0
