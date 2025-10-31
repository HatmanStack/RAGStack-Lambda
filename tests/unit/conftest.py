"""Unit tests conftest for Lambda function test isolation.

This conftest file provides session-level setup for unit tests.
Note: The 18 remaining test failures are due to sys.modules['index'] caching
across test files. This is a pre-existing test architecture issue that would
require significant refactoring to fix (renaming modules or custom import hooks).
Tests pass individually but fail when run together due to module pollution.
"""

import sys


def pytest_sessionstart(session):
    """Initialize the test session.

    Runs once at the start of the test session to clean any previously
    cached Lambda modules.
    """
    # Remove any cached index module from a previous test run
    if "index" in sys.modules:
        del sys.modules["index"]
