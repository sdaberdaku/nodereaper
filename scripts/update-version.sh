#!/bin/bash

# Script to update version across all files before creating a release tag
# Usage: ./scripts/update-version.sh <version>
# Example: ./scripts/update-version.sh 1.0.1

set -e

if [ $# -ne 1 ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 1.0.1"
    exit 1
fi

NEW_VERSION="$1"
NEW_TAG="v$NEW_VERSION"

# Validate version format (semantic versioning)
if ! echo "$NEW_VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.-]+)?$'; then
    echo "❌ Invalid version format. Use semantic versioning (e.g., 1.0.1, 1.0.0-beta.1)"
    exit 1
fi

echo "🔄 Updating version to $NEW_VERSION..."

# Update pyproject.toml
echo "📝 Updating pyproject.toml..."
sed -i.bak "s/^version = .*/version = \"$NEW_VERSION\"/" pyproject.toml

# Update src/nodereaper/__init__.py
echo "📝 Updating src/nodereaper/__init__.py..."
sed -i.bak "s/__version__ = .*/__version__ = \"$NEW_VERSION\"/" src/nodereaper/__init__.py

# Update Helm chart
echo "📝 Updating helm/Chart.yaml..."
sed -i.bak "s/^version:.*/version: $NEW_VERSION/" helm/Chart.yaml
sed -i.bak "s/^appVersion:.*/appVersion: \"$NEW_TAG\"/" helm/Chart.yaml

# Clean up backup files
rm -f pyproject.toml.bak src/nodereaper/__init__.py.bak helm/Chart.yaml.bak

echo "✅ Version updated to $NEW_VERSION in all files"
echo ""
echo "📋 Summary of changes:"
echo "  - pyproject.toml: version = \"$NEW_VERSION\""
echo "  - src/nodereaper/__init__.py: __version__ = \"$NEW_VERSION\""
echo "  - helm/Chart.yaml: version: $NEW_VERSION"
echo "  - helm/Chart.yaml: appVersion: \"$NEW_TAG\""
echo ""
echo "🚀 Next steps:"
echo "  1. Review the changes: git diff"
echo "  2. Commit the changes: git add . && git commit -m \"Bump version to $NEW_VERSION\""
echo "  3. Create and push the tag: git tag $NEW_TAG && git push origin $NEW_TAG"
echo "  4. The release workflow will automatically trigger and validate versions"
