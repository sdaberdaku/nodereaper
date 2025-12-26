"""
Pytest configuration for NodeReaper tests.

SPDX-License-Identifier: Apache-2.0
Copyright 2025 Sebastian Daberdaku
"""

import os
import sys
from pathlib import Path

import pytest

# Add src directory to Python path for imports
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment variables."""
    # Ensure tests run in safe mode
    os.environ["DRY_RUN"] = "true"
    os.environ["LOG_LEVEL"] = "DEBUG"
    os.environ["ENABLE_JSON_LOGS"] = "false"


@pytest.fixture
def mock_kubernetes_config():
    """Mock Kubernetes configuration for tests that don't need real cluster."""
    return {
        "dry_run": True,
        "node_min_age": "1s",
        "deletion_timeout": "5m",
        "cluster_name": "test-cluster",
        "log_level": "DEBUG",
        "enable_json_logs": False,
    }


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires Kubernetes cluster)"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add integration marker to tests in integration directory
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
