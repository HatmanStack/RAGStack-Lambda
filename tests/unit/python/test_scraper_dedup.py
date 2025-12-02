"""Unit tests for content deduplication."""

from unittest.mock import MagicMock, patch

import pytest

from ragstack_common.scraper.dedup import (
    DeduplicationService,
    compute_content_hash,
    normalize_content_for_hash,
    normalize_url_for_hash,
    should_skip_page,
)


class TestComputeContentHash:
    """Tests for compute_content_hash function."""

    def test_returns_sha256_hex(self):
        content = "Hello, World!"
        hash_value = compute_content_hash(content)
        # SHA-256 produces 64 hex characters
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_same_content_same_hash(self):
        content = "Test content"
        hash1 = compute_content_hash(content)
        hash2 = compute_content_hash(content)
        assert hash1 == hash2

    def test_different_content_different_hash(self):
        hash1 = compute_content_hash("Content A")
        hash2 = compute_content_hash("Content B")
        assert hash1 != hash2

    def test_empty_content(self):
        hash_value = compute_content_hash("")
        # SHA-256 of empty string
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert hash_value == expected


class TestShouldSkipPage:
    """Tests for should_skip_page function."""

    def test_new_page_not_skipped(self):
        assert should_skip_page("abc123", None) is False

    def test_same_hash_skipped(self):
        assert should_skip_page("abc123", "abc123") is True

    def test_different_hash_not_skipped(self):
        assert should_skip_page("abc123", "def456") is False


class TestNormalizeUrlForHash:
    """Tests for normalize_url_for_hash function."""

    def test_removes_fragments(self):
        url = "https://example.com/page#section"
        normalized = normalize_url_for_hash(url)
        assert "#" not in normalized
        assert normalized == "https://example.com/page"

    def test_removes_query_params(self):
        url = "https://example.com/page?foo=bar&baz=qux"
        normalized = normalize_url_for_hash(url)
        assert "?" not in normalized
        assert normalized == "https://example.com/page"

    def test_normalizes_case(self):
        url = "HTTPS://EXAMPLE.COM/Page"
        normalized = normalize_url_for_hash(url)
        assert "example.com" in normalized
        # Path case is preserved
        assert "/Page" in normalized

    def test_removes_trailing_slash(self):
        url = "https://example.com/page/"
        normalized = normalize_url_for_hash(url)
        assert normalized == "https://example.com/page"

    def test_preserves_root_path(self):
        url = "https://example.com/"
        normalized = normalize_url_for_hash(url)
        # Root path is either "/" or ""
        assert "example.com" in normalized


class TestNormalizeContentForHash:
    """Tests for normalize_content_for_hash function."""

    def test_removes_frontmatter(self):
        content = """---
source_url: https://example.com
scraped_at: 2024-01-01T00:00:00Z
---

# Title

Content here
"""
        normalized = normalize_content_for_hash(content)
        assert "source_url" not in normalized
        assert "scraped_at" not in normalized
        assert "Title" in normalized
        assert "Content" in normalized

    def test_normalizes_whitespace(self):
        content = "Hello    world\n\n\n\nMore   text"
        normalized = normalize_content_for_hash(content)
        assert "    " not in normalized  # Multiple spaces collapsed
        assert "\n\n" not in normalized  # Multiple newlines collapsed

    def test_same_content_different_frontmatter(self):
        content1 = """---
scraped_at: 2024-01-01T00:00:00Z
---
# Title
Content
"""
        content2 = """---
scraped_at: 2024-01-02T00:00:00Z
---
# Title
Content
"""
        normalized1 = normalize_content_for_hash(content1)
        normalized2 = normalize_content_for_hash(content2)
        assert normalized1 == normalized2


class TestDeduplicationService:
    """Tests for DeduplicationService class."""

    @patch("ragstack_common.scraper.dedup.boto3")
    def test_init_creates_table_reference(self, mock_boto3):
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        service = DeduplicationService("test-table")

        mock_boto3.resource.assert_called_once_with("dynamodb", region_name=None)
        mock_dynamodb.Table.assert_called_once_with("test-table")

    @patch("ragstack_common.scraper.dedup.boto3")
    def test_get_existing_hash_returns_hash(self, mock_boto3):
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [{"content_hash": "abc123"}]
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        service = DeduplicationService("test-table")
        result = service.get_existing_hash("https://example.com/page")

        assert result == "abc123"
        mock_table.query.assert_called_once()

    @patch("ragstack_common.scraper.dedup.boto3")
    def test_get_existing_hash_returns_none_for_new_url(self, mock_boto3):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        service = DeduplicationService("test-table")
        result = service.get_existing_hash("https://example.com/new")

        assert result is None

    @patch("ragstack_common.scraper.dedup.boto3")
    def test_is_content_changed_new_url(self, mock_boto3):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        service = DeduplicationService("test-table")
        result = service.is_content_changed(
            "https://example.com/new",
            "# New content\n\nSome text"
        )

        assert result is True

    @patch("ragstack_common.scraper.dedup.boto3")
    def test_is_content_changed_same_content(self, mock_boto3):
        content = "# Title\n\nContent body here"
        normalized = normalize_content_for_hash(content)
        existing_hash = compute_content_hash(normalized)

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [{"content_hash": existing_hash}]
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        service = DeduplicationService("test-table")
        result = service.is_content_changed(
            "https://example.com/page",
            content
        )

        assert result is False

    @patch("ragstack_common.scraper.dedup.boto3")
    def test_is_content_changed_different_content(self, mock_boto3):
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [{"content_hash": "old_hash_value"}]
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        service = DeduplicationService("test-table")
        result = service.is_content_changed(
            "https://example.com/page",
            "# New content\n\nDifferent text"
        )

        assert result is True

    @patch("ragstack_common.scraper.dedup.boto3")
    def test_store_hash_updates_dynamodb(self, mock_boto3):
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        service = DeduplicationService("test-table")
        service.store_hash(
            "job-123",
            "https://example.com/page",
            "# Content\n\nBody text"
        )

        mock_table.update_item.assert_called_once()
        call_kwargs = mock_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {
            "job_id": "job-123",
            "url": "https://example.com/page"
        }
        assert "content_hash" in call_kwargs["UpdateExpression"]
        assert "url_hash" in call_kwargs["UpdateExpression"]

    @patch("ragstack_common.scraper.dedup.boto3")
    def test_get_content_hash(self, mock_boto3):
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        service = DeduplicationService("test-table")

        content = "# Title\n\nBody"
        hash1 = service.get_content_hash(content)
        hash2 = service.get_content_hash(content)

        assert hash1 == hash2
        assert len(hash1) == 64


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
