"""Unit tests conftest for Lambda function test isolation.

This conftest file provides setup for unit tests.

Note on the 18 remaining failures:
- Root cause: sys.modules['index'] caching across test files
- Timing: Test modules are imported during pytest's collection phase
- Each test file adds its Lambda directory to sys.path, then does `import index`
- When the next test file does the same, Python returns the cached module instead
- Result: test_generate_embeddings gets configuration_resolver's index module

Why pytest hooks can't fix this:
- pytest_sessionstart: runs AFTER sys.modules is populated from initial imports
- pytest_collection: runs AFTER test modules have been imported
- pytest_runtest_setup: too late, modules already cached

Proper solutions (would require refactoring):
- Rename modules: index_gen_embeddings.py, index_process_doc.py, etc.
- Use importlib at module level: spec_from_file_location() instead of import
- Move Lambda code into shared lib and test that instead
- Use sys.modules cleanup at module level (before import), not in conftest
"""

import sys


def pytest_sessionstart(session):
    """Initialize the test session.

    Cleans any cached modules from a previous test run or interactive session.
    """
    if "index" in sys.modules:
        del sys.modules["index"]
