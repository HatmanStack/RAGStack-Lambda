"""Unit tests for query_kb Lambda source extraction."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add Lambda source directory to path
sys.path.insert(0, str(Path(__file__).parents[3] / "src" / "lambda" / "query_kb"))


class TestExtractSourceUrlFromContent:
    """Tests for extract_source_url_from_content function."""

    @pytest.fixture(autouse=True)
    def _mock_boto3(self):
        """Mock boto3 clients to avoid AWS initialization."""
        with patch.dict(
            "sys.modules",
            {
                "boto3": MagicMock(),
            },
        ):
            # Need to mock config manager too
            mock_config = MagicMock()
            mock_config.get_parameter.return_value = False
            with patch("ragstack_common.config.ConfigurationManager", return_value=mock_config):
                yield

    def test_extracts_url_from_frontmatter(self):
        # Import inside test after mocking
        import importlib

        import index

        importlib.reload(index)

        content = """---
source_url: https://docs.example.com/page1
scraped_at: 2025-01-01T00:00:00Z
title: "Test Page"
---

# Test Page

Some content here.
"""
        result = index.extract_source_url_from_content(content)
        assert result == "https://docs.example.com/page1"

    def test_extracts_url_with_quotes(self):
        import importlib

        import index

        importlib.reload(index)

        content = """---
source_url: "https://docs.example.com/page2"
---

Content
"""
        result = index.extract_source_url_from_content(content)
        assert result == "https://docs.example.com/page2"

    def test_returns_none_for_no_frontmatter(self):
        import importlib

        import index

        importlib.reload(index)

        content = """# Just a regular markdown file

No frontmatter here.
"""
        result = index.extract_source_url_from_content(content)
        assert result is None

    def test_returns_none_for_empty_content(self):
        import importlib

        import index

        importlib.reload(index)

        result = index.extract_source_url_from_content("")
        assert result is None

    def test_returns_none_for_none_content(self):
        import importlib

        import index

        importlib.reload(index)

        result = index.extract_source_url_from_content(None)
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
