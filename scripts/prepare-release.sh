#!/bin/bash
# Prepare a new release: updates versions, runs tests, verifies consistency
# Usage: ./scripts/prepare-release.sh <version>

set -e

VERSION="$1"

if [[ -z "$VERSION" ]]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 1.2.0"
    exit 1
fi

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "❌ Invalid version format. Use semantic versioning (e.g., 1.2.0)"
    exit 1
fi

echo "🚀 Preparing release $VERSION..."

# Update versions
sed -i "s/version = \".*\"/version = \"$VERSION\"/" pyproject.toml
sed -i "s/version: .*/version: $VERSION/" helm/Chart.yaml
sed -i "s/appVersion: .*/appVersion: \"v$VERSION\"/" helm/Chart.yaml
sed -i "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" src/nodereaper/__init__.py
sed -i "s/Version-[0-9.]*/Version-$VERSION/g" helm/README.md
sed -i "s/AppVersion-v[0-9.]*/AppVersion-v$VERSION/g" helm/README.md

# Verify and test
./scripts/check-version.sh "$VERSION"
python -m pytest tests/ -q
helm lint helm/

echo ""
echo "✅ Release $VERSION ready!"
echo ""
echo "Next steps:"
echo "  git add . && git commit -m 'Release v$VERSION'"
echo "  git tag v$VERSION"
echo "  git push origin main && git push origin v$VERSION"
