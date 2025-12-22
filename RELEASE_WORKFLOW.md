# NodeReaper Release Workflow

This document explains the streamlined release process for NodeReaper.

## 📋 Scripts Overview

We use **2 scripts** for version management:

### 1. `scripts/check-version.sh` - Version Verification
**Purpose**: Verify version consistency across all files

```bash
# Check current versions and consistency
./scripts/check-version.sh

# Check if all files match a specific version
./scripts/check-version.sh 1.2.0
```

**Use cases:**
- CI/CD pipeline validation
- Manual verification before release
- Debugging version mismatches

### 2. `scripts/prepare-release.sh` - Complete Release Preparation
**Purpose**: One-stop script for preparing a new release

```bash
# Prepare a new release
./scripts/prepare-release.sh 1.2.0
```

**What it does:**
1. ✅ Validates version format
2. ✅ Checks git branch and status
3. ✅ Updates all version files
4. ✅ Verifies version consistency
5. ✅ Runs tests
6. ✅ Lints Helm chart
7. ✅ Provides release checklist

## 🚀 Release Process

### Step 1: Prepare Release
```bash
./scripts/prepare-release.sh 1.2.0
```

### Step 2: Review Changes
```bash
git diff
```

### Step 3: Update Changelog (if needed)
Edit `CHANGELOG.md` to add release notes.

### Step 4: Commit and Tag
```bash
git add .
git commit -m "Release v1.2.0"
git tag v1.2.0
```

### Step 5: Push
```bash
git push origin main
git push origin v1.2.0
```

### Step 6: Automated Release
GitHub Actions will automatically:
- Build multi-arch Docker images
- Publish to GitHub Container Registry
- Create GitHub release
- Update Helm chart repository

## 🔍 Version Consistency

All version numbers are kept in sync across:

| File | Format | Example |
|------|--------|---------|
| `pyproject.toml` | `version = "X.Y.Z"` | `version = "1.2.0"` |
| `src/nodereaper/__init__.py` | `__version__ = "X.Y.Z"` | `__version__ = "1.2.0"` |
| `helm/Chart.yaml` | `version: X.Y.Z` | `version: 1.2.0` |
| `helm/Chart.yaml` | `appVersion: "vX.Y.Z"` | `appVersion: "v1.2.0"` |
| `helm/README.md` | Badge versions | Auto-updated |

## 🛠️ CI/CD Integration

### Pre-commit Hook (Optional)
```bash
# Add to .git/hooks/pre-commit
#!/bin/bash
./scripts/check-version.sh
```

### GitHub Actions
The `check-version.sh` script can be used in CI:

```yaml
- name: Check version consistency
  run: ./scripts/check-version.sh
```

## 🔄 Migration from Old Scripts

**Removed**: `scripts/update-version.sh` (redundant)
**Kept**:
- `scripts/check-version.sh` (verification)
- `scripts/prepare-release.sh` (complete preparation)

This provides a cleaner, more maintainable workflow with less duplication.

## 🎯 Quick Reference

| Task | Command |
|------|---------|
| Check versions | `./scripts/check-version.sh` |
| Prepare release | `./scripts/prepare-release.sh X.Y.Z` |
| Verify specific version | `./scripts/check-version.sh X.Y.Z` |
