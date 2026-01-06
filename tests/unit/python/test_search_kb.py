"""Unit tests for search_kb Lambda filter integration.

Tests the filter generation integration in the search_kb Lambda function.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Path to search_kb Lambda
SEARCH_KB_PATH = str(Path(__file__).parents[3] / "src" / "lambda" / "search_kb")


@pytest.fixture
def search_kb_module():
    """Import search_kb index module with proper path setup and cleanup."""
    # Add path temporarily
    sys.path.insert(0, SEARCH_KB_PATH)

    # Remove cached index if it exists from another Lambda
    if "index" in sys.modules:
        del sys.modules["index"]

    # Mock boto3 clients to avoid AWS initialization
    mock_boto3 = MagicMock()
    mock_dynamodb = MagicMock()

    with patch.dict(
        "sys.modules",
        {
            "boto3": mock_boto3,
            "boto3.dynamodb": mock_dynamodb,
        },
    ):
        mock_config = MagicMock()
        mock_config.get_parameter.return_value = False
        with patch("ragstack_common.config.ConfigurationManager", return_value=mock_config):
            import index

            yield index

    # Clean up
    sys.path.remove(SEARCH_KB_PATH)
    if "index" in sys.modules:
        del sys.modules["index"]


class TestSearchKBFilterIntegration:
    """Tests for filter generation integration in search_kb Lambda."""

    def test_filter_components_lazy_loaded(self, search_kb_module):
        """Test that filter components are lazy-loaded."""
        # Access the module-level variables
        assert search_kb_module._key_library is None
        assert search_kb_module._filter_generator is None
        assert search_kb_module._multislice_retriever is None

    def test_filter_examples_cache_ttl_configured(self, search_kb_module):
        """Test that filter examples cache TTL is configured."""
        # Check that the TTL is set to 5 minutes (300 seconds)
        assert search_kb_module.FILTER_EXAMPLES_CACHE_TTL == 300


class TestGetFilterExamples:
    """Tests for _get_filter_examples function."""

    def test_get_filter_examples_returns_list(self, search_kb_module):
        """Test that _get_filter_examples returns a list."""
        # Reset cache
        search_kb_module._filter_examples_cache = None
        search_kb_module._filter_examples_cache_time = None

        result = search_kb_module._get_filter_examples()

        assert isinstance(result, list)

    def test_get_filter_examples_uses_cache(self, search_kb_module):
        """Test that _get_filter_examples uses cached values."""
        import time

        # Set up cache
        cached_examples = [{"query": "test", "filter": {"key": {"$eq": "value"}}}]
        search_kb_module._filter_examples_cache = cached_examples
        search_kb_module._filter_examples_cache_time = time.time()

        result = search_kb_module._get_filter_examples()

        # Should return cached value
        assert result == cached_examples


class TestSearchConsistencyWithQuery:
    """Tests to ensure search_kb behavior is consistent with query_kb."""

    def test_search_has_filter_generation_config_check(self):
        """Test that search_kb checks filter_generation_enabled config."""
        # Verify the config parameter names are used in source
        source_path = Path(__file__).parents[3] / "src/lambda/search_kb/index.py"
        with open(source_path) as f:
            source = f.read()
        assert "filter_generation_enabled" in source
        assert "multislice_enabled" in source

    def test_search_has_filter_applied_response(self):
        """Test that search_kb includes filterApplied in response."""
        source_path = Path(__file__).parents[3] / "src/lambda/search_kb/index.py"
        with open(source_path) as f:
            source = f.read()
        assert "filterApplied" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
