"""Global pytest configuration for all tests."""

import os


def pytest_configure(config):
    """Set environment variables before any test collection or execution."""
    os.environ.setdefault("AWS_REGION", "us-east-1")
    os.environ.setdefault("REGION", "us-east-1")
