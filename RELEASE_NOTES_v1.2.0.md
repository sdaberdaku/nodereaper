# NodeReaper v1.2.0 Release Notes

## 🎉 What's New

NodeReaper v1.2.0 introduces significant improvements to configuration consistency and matching precision, making it more reliable and easier to configure.

## 🔄 Breaking Changes

### Configuration Format Changes

**`nodeLabelSelector` is now a map instead of a list:**

```yaml
# Before (v1.1.0)
config:
  nodeLabelSelector:
    - "cleanup-enabled=true"
    - "instance-type=m5.large"

# After (v1.2.0)
config:
  nodeLabelSelector:
    cleanup-enabled: "true"
    instance-type: "m5.large"
```

### Exact Matching for All Configurations

All matching operations now use **exact matching** instead of pattern matching for improved precision and predictability:

- **Finalizer Lists**: `finalizerWhitelist` and `finalizerBlacklist` now match exact finalizer names
- **Deletion Taints**: `deletionTaints` now match exact taint keys
- **Protection**: `protectionAnnotations` and `protectionLabels` use exact key-value pairs

## ✨ New Features

### Protection Labels
- Added `protectionLabels` configuration for permanent node protection using exact label key-value matching
- Works alongside existing `protectionAnnotations` for comprehensive protection strategies

### Enhanced Configuration Validation
- Improved error handling and validation for all configuration formats
- Better type handling in Helm templates (strings, numbers, booleans)
- More descriptive error messages for configuration issues

## 🛠️ Improvements

### Default Configuration Updates
- Streamlined `deletionTaints` to include only essential taint keys:
  - `karpenter.sh/disrupted`
  - `node.kubernetes.io/unreachable`
  - `node.kubernetes.io/unschedulable`

### Test Infrastructure
- Enhanced cluster verification in test scripts
- Updated all tests to use new configuration formats
- Comprehensive test coverage for exact matching functionality

### Documentation
- Updated README with new configuration examples
- Added comprehensive configuration reference
- Improved troubleshooting documentation
- Updated Helm chart documentation

## 🐛 Bug Fixes

- Fixed Helm template coalesce warnings when using map-based configurations
- Resolved test script compatibility with new configuration format
- Improved template logic for handling different value types

## 📦 Installation

### Helm Chart
```bash
helm install nodereaper oci://ghcr.io/sdaberdaku/charts/nodereaper \
  --version 1.2.0 \
  --namespace nodereaper \
  --create-namespace
```

### Docker Image
```bash
docker pull ghcr.io/sdaberdaku/nodereaper:v1.2.0
```

## 🔄 Migration Guide

### Updating nodeLabelSelector

If you're using `nodeLabelSelector`, update your configuration:

```yaml
# Old format (will cause errors in v1.2.0)
config:
  nodeLabelSelector:
    - "environment=production"
    - "node-type=worker"

# New format
config:
  nodeLabelSelector:
    environment: "production"
    node-type: "worker"
```

### Reviewing Exact Matching

Review your configuration to ensure exact matching works as expected:

- **Finalizers**: Ensure `finalizerWhitelist`/`finalizerBlacklist` contain exact finalizer names
- **Taints**: Verify `deletionTaints` contain exact taint keys (no wildcards)
- **Protection**: Check that `protectionAnnotations`/`protectionLabels` have exact key-value pairs

## 🔗 Links

- [Full Changelog](https://github.com/sdaberdaku/nodereaper/blob/main/CHANGELOG.md)
- [Documentation](https://github.com/sdaberdaku/nodereaper)
- [Helm Chart](https://github.com/sdaberdaku/nodereaper/tree/main/helm)
- [Docker Images](https://github.com/sdaberdaku/nodereaper/pkgs/container/nodereaper)

## 🙏 Contributors

- [@sdaberdaku](https://github.com/sdaberdaku)

---

**Full Changelog**: https://github.com/sdaberdaku/nodereaper/compare/v1.1.0...v1.2.0
