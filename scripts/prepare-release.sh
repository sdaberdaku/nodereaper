#!/bin/bash

# Script to prepare a new release
# Usage: ./scripts/prepare-release.sh <version>

set -e

VERSION="$1"

if [[ -z "$VERSION" ]]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 1.2.0"
    exit 1
fi

echo "🚀 Preparing release $VERSION..."

# Validate version format
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "❌ Invalid version format. Use semantic versioning (e.g., 1.2.0)"
    exit 1
fi

# Check if we're on main branch
CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" != "main" ]]; then
    echo "⚠️  Warning: You're not on the main branch (current: $CURRENT_BRANCH)"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "❌ You have uncommitted changes. Please commit or stash them first."
    exit 1
fi

echo "📝 Updating version numbers..."

# Update pyproject.toml
sed -i "s/version = \".*\"/version = \"$VERSION\"/" pyproject.toml

# Update Helm Chart.yaml
sed -i "s/version: .*/version: $VERSION/" helm/Chart.yaml
sed -i "s/appVersion: .*/appVersion: \"v$VERSION\"/" helm/Chart.yaml

# Update Python package version
sed -i "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" src/nodereaper/__init__.py

# Update Helm README badges
sed -i "s/Version-[0-9.]*/Version-$VERSION/g" helm/README.md
sed -i "s/AppVersion-v[0-9.]*/AppVersion-v$VERSION/g" helm/README.md

echo "🔍 Verifying version consistency..."
./scripts/check-version.sh "$VERSION"

echo "🧪 Running tests..."
python -m pytest tests/ -q

echo "🔍 Linting Helm chart..."
helm lint helm/

echo "📋 Release checklist:"
echo "  ✅ Version numbers updated and verified"
echo "  ✅ Tests passing"
echo "  ✅ Helm chart valid"
echo "  📝 Update CHANGELOG.md with release notes"
echo "  📝 Review and commit changes"
echo "  📝 Create and push git tag: git tag v$VERSION && git push origin v$VERSION"
echo "  📝 GitHub Actions will automatically build and publish the release"

echo ""
echo "🎉 Release $VERSION is ready!"
echo ""
echo "Next steps:"
echo "  1. Review the changes: git diff"
echo "  2. Update CHANGELOG.md if needed"
echo "  3. Commit changes: git add . && git commit -m 'Release v$VERSION'"
echo "  4. Create tag: git tag v$VERSION"
echo "  5. Push: git push origin main && git push origin v$VERSION"
