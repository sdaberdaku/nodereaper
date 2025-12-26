#!/bin/bash

# Script to check version consistency across all files
# Usage: ./scripts/check-version.sh [version]
# If version is provided, checks if all files match that version
# If no version provided, shows current versions in all files

set -e

TARGET_VERSION="$1"

echo "🔍 Checking version consistency..."
echo ""

# Get versions from files
PYPROJECT_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
INIT_VERSION=$(grep '^__version__ = ' src/nodereaper/__init__.py | sed 's/__version__ = "\(.*\)"/\1/')
CHART_VERSION=$(grep '^version:' helm/Chart.yaml | sed 's/version: //')
CHART_APP_VERSION=$(grep '^appVersion:' helm/Chart.yaml | sed 's/appVersion: "\(.*\)"/\1/')

echo "📋 Current versions:"
echo "  pyproject.toml:             $PYPROJECT_VERSION"
echo "  src/nodereaper/__init__.py: $INIT_VERSION"
echo "  helm/Chart.yaml version:    $CHART_VERSION"
echo "  helm/Chart.yaml appVersion: $CHART_APP_VERSION"
echo ""

# Check consistency
INCONSISTENT=false

if [ "$PYPROJECT_VERSION" != "$INIT_VERSION" ]; then
    echo "❌ pyproject.toml version ($PYPROJECT_VERSION) != __init__.py version ($INIT_VERSION)"
    INCONSISTENT=true
fi

if [ "$PYPROJECT_VERSION" != "$CHART_VERSION" ]; then
    echo "❌ pyproject.toml version ($PYPROJECT_VERSION) != Helm chart version ($CHART_VERSION)"
    INCONSISTENT=true
fi

EXPECTED_APP_VERSION="v$PYPROJECT_VERSION"
if [ "$EXPECTED_APP_VERSION" != "$CHART_APP_VERSION" ]; then
    echo "❌ Expected Helm appVersion ($EXPECTED_APP_VERSION) != actual appVersion ($CHART_APP_VERSION)"
    INCONSISTENT=true
fi

if [ "$TARGET_VERSION" ]; then
    echo "🎯 Checking against target version: $TARGET_VERSION"
    if [ "$PYPROJECT_VERSION" != "$TARGET_VERSION" ]; then
        echo "❌ pyproject.toml version ($PYPROJECT_VERSION) != target version ($TARGET_VERSION)"
        INCONSISTENT=true
    fi
fi

if [ "$INCONSISTENT" = true ]; then
    echo ""
    echo "❌ Version inconsistencies found!"
    echo "💡 Run ./scripts/prepare-release.sh <version> to fix and prepare release"
    exit 1
else
    echo "✅ All versions are consistent!"
    if [ "$TARGET_VERSION" ]; then
        echo "✅ All versions match target: $TARGET_VERSION"
    fi
fi
