#!/bin/bash

# Script to set up development environment for NodeReaper
# Installs dependencies, sets up pre-commit hooks, and prepares for development

set -e

echo "🚀 Setting up NodeReaper development environment..."

# Install development dependencies first (includes tools like setuptools, wheel, etc.)
echo "📦 Installing development dependencies..."
pip install -r requirements-dev.txt

# Install the package in editable mode (after dev tools are available)
echo "📦 Installing NodeReaper in editable mode..."
pip install -e .

# Set up pre-commit hooks (skip in CI environments)
if [[ "${CI:-false}" == "true" || "${GITHUB_ACTIONS:-false}" == "true" ]]; then
    echo "⏭️  Skipping pre-commit hooks setup (CI environment detected)"
else
    echo "🔧 Setting up pre-commit hooks..."
    pre-commit install --install-hooks
fi

echo "✅ Development environment setup complete!"
echo ""
echo "🎉 You're ready to develop NodeReaper!"
echo ""
echo "💡 Next steps:"
echo "   - Run tests: make test"
echo "   - Set up test cluster: make setup-test-cluster"
echo "   - Run integration tests: make test-integration"
echo "   - Format code: make format"
echo "   - Run all checks: make all-checks"
